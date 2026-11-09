// Export source-backed map/render anchors from the original imported ELF.
// Labels are research roles, not recovered original C++ symbol names.
// @category OC2.Research
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import com.google.gson.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

public class OC2MapFlow extends GhidraScript {
    private final Gson gson = new GsonBuilder().setPrettyPrinting().create();
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("manifest.json and ignored output directory required");
        JsonObject manifest = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        String sha = currentProgram.getExecutableSHA256();
        if (!manifest.get("nativeSHA256").getAsString().equalsIgnoreCase(sha))
            throw new IllegalStateException("Imported ELF fingerprint differs from original source");
        if (currentProgram.getImageBase().getOffset() != 0)
            throw new IllegalStateException("Original addresses require ELF image base zero");
        Path output = Path.of(args[1]);
        Files.createDirectories(output.resolve("decompiled"));
        JsonArray rows = new JsonArray();
        FunctionManager functions = currentProgram.getFunctionManager();
        AddressFactory addresses = currentProgram.getAddressFactory();
        for (JsonElement element : manifest.getAsJsonArray("anchors")) {
            monitor.checkCancelled();
            JsonObject input = element.getAsJsonObject();
            Address at = addresses.getDefaultAddressSpace().getAddress(input.get("address").getAsString());
            byte[] sourceBytes = new byte[input.get("unwindBytes").getAsInt()];
            currentProgram.getMemory().getBytes(at, sourceBytes);
            String actual = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(sourceBytes));
            if (!actual.equals(input.get("originalFunctionSHA256").getAsString()))
                throw new IllegalStateException("Ghidra memory differs from original ELF at " + at);
            AddressSet sourceRange = new AddressSet(at, at.add(sourceBytes.length-1));
            JsonArray boundaryChanges = new JsonArray();
            // The stripped ELF's unwind table supplies stronger boundaries than
            // auto-analysis. Only correct generated functions or our own labels.
            List<Function> overlaps = new ArrayList<>();
            functions.getFunctionsOverlapping(sourceRange).forEachRemaining(overlaps::add);
            for (Function overlap : overlaps) {
                if (overlap.getEntryPoint().equals(at)) continue;
                SourceType source = overlap.getSymbol().getSource();
                if (source != SourceType.DEFAULT && source != SourceType.ANALYSIS &&
                    !overlap.getName().startsWith("oc2r_"))
                    throw new IllegalStateException("Preserve manually named overlapping function " + overlap.getName());
                JsonObject change = new JsonObject();
                change.addProperty("entry", overlap.getEntryPoint().toString());
                change.addProperty("priorName", overlap.getName());
                change.addProperty("priorBody", overlap.getBody().toString());
                if (sourceRange.contains(overlap.getEntryPoint())) {
                    functions.removeFunction(overlap.getEntryPoint());
                    change.addProperty("action", "remove generated internal function; original unwind has one function here");
                } else {
                    overlap.setBody(overlap.getBody().subtract(sourceRange));
                    change.addProperty("action", "trim generated overlap to preserve original unwind range");
                }
                boundaryChanges.add(change);
            }
            Function function = functions.getFunctionAt(at);
            boolean created = false;
            if (function == null) {
                DisassembleCommand disassemble = new DisassembleCommand(at, sourceRange, true);
                if (!disassemble.applyTo(currentProgram, monitor))
                    throw new IllegalStateException("Could not disassemble original anchor " + at);
                function = functions.createFunction(input.get("researchLabel").getAsString(), at,
                                                    sourceRange, SourceType.USER_DEFINED);
                created = true;
            }
            String priorBody = function.getBody().toString();
            if (function.getSymbol().getSource() == SourceType.USER_DEFINED &&
                !function.getName().startsWith("oc2r_"))
                throw new IllegalStateException("Preserve manually named anchor " + function.getName());
            function.setBody(sourceRange);
            String oldName = function.getName();
            function.setName(input.get("researchLabel").getAsString(), SourceType.USER_DEFINED);
            String note = "OC2 source-backed research role; NOT an original C++ symbol.\nStage: " +
                input.get("stage").getAsString() + "\nOriginal ARM64 SHA256: " + sha +
                "\nOriginal unwind size: " + input.get("unwindBytes").getAsString() +
                "\nStatic analysis only; complete runtime/rendering is not inferred.";
            String priorComment = function.getComment();
            if (priorComment == null || priorComment.isEmpty()) function.setComment(note);
            else if (!priorComment.contains(note)) function.setComment(priorComment+"\n\n"+note);
            currentProgram.getBookmarkManager().setBookmark(at, BookmarkType.NOTE, "OC2 Map-to-draw",
                input.get("stage").getAsString()+": "+input.get("researchLabel").getAsString());
            JsonObject row = input.deepCopy();
            row.addProperty("priorGhidraName", oldName);
            row.addProperty("createdFromOriginalUnwindRange", created);
            row.addProperty("priorGhidraBody", priorBody);
            row.add("overlapCorrections", boundaryChanges);
            rows.add(row);
        }
        DecompInterface decompiler = new DecompInterface();
        decompiler.toggleCCode(true);
        decompiler.openProgram(currentProgram);
        int completed = 0;
        try {
            for (JsonElement element : rows) {
                monitor.checkCancelled();
                JsonObject row = element.getAsJsonObject();
                Address at = addresses.getDefaultAddressSpace().getAddress(row.get("address").getAsString());
                Function function = functions.getFunctionAt(at);
                DecompileResults result = decompiler.decompileFunction(function, 45, monitor);
                boolean ok = result.decompileCompleted() && result.getDecompiledFunction() != null;
                row.addProperty("decompileCompleted", ok);
                row.addProperty("decompileMessage", result.getErrorMessage());
                if (ok) {
                    String file = row.get("address").getAsString()+".c";
                    Files.writeString(output.resolve("decompiled").resolve(file),
                        "/* Ghidra approximation of ORIGINAL ELF; not original source or executable replacement. */\n" +
                        result.getDecompiledFunction().getC(), StandardCharsets.UTF_8);
                    row.addProperty("decompiledFile", "decompiled/"+file);
                    completed++;
                }
                JsonArray callers = new JsonArray();
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(at);
                while (refs.hasNext()) {
                    Reference ref = refs.next();
                    JsonObject call = new JsonObject();
                    call.addProperty("from", ref.getFromAddress().toString());
                    call.addProperty("type", ref.getReferenceType().toString());
                    Function caller = functions.getFunctionContaining(ref.getFromAddress());
                    if (caller != null) {
                        call.addProperty("function", caller.getEntryPoint().toString());
                        call.addProperty("name", caller.getName());
                    }
                    callers.add(call);
                }
                row.add("referencesToEntry", callers);
                JsonArray calls = new JsonArray();
                for (Function called : function.getCalledFunctions(monitor)) {
                    JsonObject callee = new JsonObject();
                    callee.addProperty("entry", called.getEntryPoint().toString());
                    callee.addProperty("name", called.getName());
                    calls.add(callee);
                }
                row.add("calledFunctions", calls);
                println("OC2_EXPORT "+at+" "+function.getName()+" decompiled="+ok);
            }
        } finally { decompiler.dispose(); }
        JsonObject report = new JsonObject();
        report.addProperty("format", "oc2-ghidra-map-flow-v1");
        report.addProperty("manifestID", manifest.get("manifestID").getAsString());
        report.addProperty("nativeSHA256", sha);
        report.addProperty("imageBase", currentProgram.getImageBase().toString());
        report.addProperty("language", currentProgram.getLanguageID().toString());
        report.addProperty("compilerSpec", currentProgram.getCompilerSpec().getCompilerSpecID().toString());
        report.addProperty("functionCount", functions.getFunctionCount());
        report.addProperty("anchorCount", rows.size());
        report.addProperty("decompiledAnchorCount", completed);
        report.addProperty("labelsAreResearchRoles", true);
        report.addProperty("renderedFrameObserved", false);
        report.add("anchors", rows);
        Files.writeString(output.resolve("ghidra-report.json"), gson.toJson(report)+"\n", StandardCharsets.UTF_8);
        println("OC2_REPORT "+output.resolve("ghidra-report.json")+" "+completed+"/"+rows.size());
    }
}
