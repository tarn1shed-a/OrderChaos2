"""Prepare/reopen an original-ELF Ghidra project and export map-to-draw anchors.

The role names are research labels. Byte identity and original unwind ranges are
checked before import; full decompilation, databases and binaries stay ignored.
"""
import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'map_request': {
        0xa34f28: 'map_request_producer', 0x539508: 'world_request_consumer',
        0x8fcb1c: 'world_open_and_packages', 0x8fd1e4: 'world_container',
        0x8fb9f8: 'world_stream_lookup', 0xa7e490: 'global_stream_entry',
    },
    'tile_streaming': {
        0x366ca0: 'tile_streaming_update', 0x367684: 'terrain_task_start',
        0x35200c: 'terrain_task_create', 0x3412a0: 'task_enqueue',
        0x354ca0: 'terrain_task_states', 0x354de4: 'terrain_source_request',
        0x358e08: 'terrain_source_read', 0x3673b0: 'tile_completion_scan',
        0x367884: 'item_task_start', 0xa5f518: 'item_task_create',
        0x3664e0: 'tile_unload', 0x352354: 'terrain_release',
    },
    'terrain_scene_and_draw': {
        0x354fec: 'terrain_mask_request', 0x35516c: 'terrain_alternate_mask_stage',
        0x355644: 'terrain_mask_stage', 0x355a38: 'terrain_lightmap_stage',
        0x355f28: 'terrain_chunk_groups', 0x3563dc: 'terrain_chunk_materials',
        0x356d34: 'terrain_dominant_layer_map', 0x356f74: 'terrain_water_stage',
        0x357618: 'terrain_navigation_stage', 0x3577ec: 'terrain_geometry_buffers',
        0x35b32c: 'terrain_manager_initialize', 0x35bb64: 'terrain_scene_initialize',
        0x35bce0: 'terrain_water_scene_initialize', 0x35be58: 'terrain_shadow_scene_initialize',
        0x12bfc28: 'terrain_scene_base_initialize',
        0x375294: 'terrain_submit_dispatch', 0x375354: 'terrain_draw_dispatch',
        0x3752a0: 'terrain_scene_submit', 0x375360: 'terrain_scene_draw',
        0x35cfb4: 'terrain_manager_draw',
        0x5473d8: 'terrain_draw_enable_branch',
        0x545ac4: 'terrain_draw_flag_initialization',
        0x54b1e0: 'terrain_draw_flag_reset',
    },
    'building_instances': {
        0xa60a60: 'item_task_states', 0xa60b4c: 'item_source_read',
        0xa61030: 'item_collision_requests', 0xa61884: 'item_lightmap_requests',
        0xa6196c: 'item_instance_create', 0xa63218: 'type2_model_create',
        0x33ebf8: 'model_owner_initialize', 0x33cfe4: 'model_task_worker',
        0x34138c: 'model_completion', 0x340dc0: 'model_slot_refresh',
        0x33e774: 'model_selected_visibility', 0x33f7b4: 'model_material_options',
    },
    'resources_and_materials': {
        0x1181778: 'resource_lookup_and_read', 0x117ec68: 'resource_constructor',
        0x148daa8: 'bres_stream_reader', 0x1180360: 'resource_dependency_processing',
        0x1118004: 'source_effect_name_lookup', 0x112330c: 'source_scene_assemble',
        0x111dae0: 'source_node_assemble', 0x111b8c4: 'source_mesh_lookup',
        0x1130fd8: 'mesh_constructor', 0x11850fc: 'material_name_lookup',
        0x112920c: 'material_effect_and_properties', 0x1127250: 'effect_create',
        0x1406e94: 'effect_compile_and_cache', 0x13baac8: 'material_constructor',
        0x33b854: 'model_material_rebuild', 0x33b48c: 'model_part_rebind',
        0x112aa88: 'part_binding_create', 0x113235c: 'part_material_set',
    },
    'scene_and_frame': {
        0x4dc648: 'world_render_frame',
        0x53b2a0: 'world_frame_update', 0x34df7c: 'renderer_frame_update',
        0x34ed98: 'renderer_draw_entry', 0x34f154: 'renderer_scene_branch',
        0x12f2318: 'primary_scene_initialize', 0x1362f6c: 'scene_node_attach',
        0x1362320: 'scene_node_matrix_update', 0x12f1378: 'scene_tree_walk',
        0x12ba4d8: 'scene_root_collect', 0x1324234: 'node_cull_and_submit',
        0x1132bc8: 'mesh_node_submit', 0x13246d8: 'accepted_node_submit',
        0x12f368c: 'scene_queue_insert',
    },
    'frame_and_presentation': {
        0x3b8dfc: 'android_app_factory', 0x14f1ef0: 'base_app_initialize',
        0x14f2078: 'android_app_impl_initialize', 0x14f17a8: 'android_frame_thread_entry',
        0x14f3c40: 'base_app_frame', 0x3ba314: 'game_app_frame',
        0x4cdf50: 'game_root_initialize', 0x4d1558: 'game_root_startup',
        0x4d5488: 'game_root_frame', 0x3323e4: 'game_device_reference',
        0x147338c: 'driver_2d_begin_guard', 0x14733fc: 'driver_2d_end_guard',
        0x142240c: 'gles_2d_begin', 0x1422604: 'gles_2d_end',
        0x4dd0c8: 'world_overlay_stage', 0x4e0168: 'world_overlay_extra_stage',
        0x32addc: 'display_frame_begin', 0x32ae94: 'display_frame_end',
        0x147329c: 'driver_frame_end', 0x14736b4: 'driver_present_dispatch',
        0x1473788: 'driver_android_present', 0x14f3e28: 'app_present_dispatch',
        0x14f40b4: 'app_singleton_get', 0x1477708: 'render_target_commit',
        0x1438f1c: 'texture_target_bind', 0x1434288: 'framebuffer_bind',
        0x5557e0: 'postprocess_material_factory',
        0x34bb58: 'bloom_targets_prepare',
        0x4d6538: 'world_draw_dispatch', 0x4d65b8: 'world_draw_and_overlays',
        0x34d7fc: 'world_renderer_initialize', 0x343394: 'postprocess_initialize',
        0x34a870: 'postprocess_frame_enable', 0x346148: 'postprocess_begin',
        0x34632c: 'postprocess_end', 0x346574: 'postprocess_prepare',
        0x349104: 'postprocess_combine', 0x34b518: 'postprocess_quad_pass',
        0x34ad74: 'postprocess_hdr_parameters',
        0x147d610: 'render_target_push', 0x147d79c: 'render_target_pop',
        0x1438458: 'default_render_target_activate', 0x14395c8: 'texture_render_target_activate',
        0x5d0e74: 'world_extra_draw_batches',
    },
    'configuration_and_gpu_resources': {
        0x3bb830: 'game_options_consume', 0x345c2c: 'postprocess_resources_initialize',
        0x3446b4: 'postprocess_target_prepare', 0x4d6040: 'game_world_update',
        0x1462ff8: 'buffer_request', 0x14509dc: 'vertex_binding_assign',
        0x1422d58: 'gles_buffer_wrapper_create', 0x1464334: 'buffer_client_data_set',
        0x14373f0: 'gles_buffer_storage_create',
        0x147f0ac: 'render_target_request', 0x1423174: 'gles_target_request',
        0x144c340: 'texture_manager_create_request', 0x143997c: 'gles_texture_storage_create',
        0x141c0c0: 'program_request_key', 0x141af90: 'program_cache_request',
        0x141d368: 'shader_stage_request', 0x14368e4: 'gles_shader_create',
        0x1432db0: 'gles_shader_compile', 0x1436534: 'gles_program_create',
        0x1432f2c: 'gles_program_link', 0x1435330: 'gles_driver_initialize',
        0x13b3430: 'driver_format_capabilities_build',
        0x13b7588: 'driver_version_and_extensions', 0x13b7ad0: 'driver_capabilities_finalize',
        0x1424b94: 'gles_program_factory', 0x1424d2c: 'gles_shader_text_factory',
        0x1422e2c: 'gles_default_target_create', 0x14f3e04: 'app_default_framebuffer_get',
        0x1473034: 'driver_frame_begin', 0x147bfac: 'driver_auxiliary_geometry_initialize',
        0x1434600: 'gles_buffer_client_upload', 0x1463d80: 'buffer_descriptor_initialize',
        0x1466f38: 'default_target_base_initialize',
        0x14390a0: 'gles_target_attachment_bind', 0x14f3e64: 'current_egl_context_check',
        0x14115ac: 'gles_driver_state_apply_dispatch', 0x1410ce8: 'gles_driver_state_apply',
        0x1472540: 'driver_default_target_publish',
    },
    'draw_queue_and_device': {
        0x12f46e0: 'scene_collect_direct', 0x12f47d8: 'scene_collect_reference',
        0x12f4bac: 'scene_pass_b0', 0x12f5770: 'scene_pass_a0',
        0x12f55a4: 'queue_sort', 0x12f6b5c: 'scene_pass_a8',
        0x12f6310: 'queue32_heap_sort', 0x12f6528: 'queue32_dispatch',
        0x147b128: 'device_pass_state',
        0x113011c: 'mesh_node_draw',
        0x1197014: 'static_mesh_b0_noop',
        0x315d18: 'driver_draw_binding', 0x1477984: 'driver_draw_guard',
        0x1478180: 'driver_draw_variant_guard',
        0x1477a08: 'driver_draw_alternate_branch',
        0x14242b0: 'gles_draw_command', 0x1424474: 'gles_draw_command_variant',
        0x142483c: 'gles_draw_command_variant2', 0x143ab50: 'gles_draw_calls',
        0x143ad38: 'gles_instanced_calls', 0x143ae7c: 'gles_instanced_call_variant',
        0x149d6a4: 'alternate_draw_command', 0x149d868: 'alternate_draw_variant',
        0x149dc30: 'alternate_draw_variant2', 0x14a7eb8: 'alternate_gl_draw_calls',
        0x14f1890: 'android_app_run_loop', 0x150039c: 'android_app_present',
    },
}


def draw_evidence(image):
    """Check a conditional original draw branch, without inventing live state."""
    relocations = {r['r_offset']: r['r_addend'] for r in
                   image.elf.get_section_by_name('.rela.dyn').iter_relocations()
                   if r['r_info_type'] == 1027}
    slots = []
    for table, slot, target in (
        (0x244e538, 0x10, 0x113011c),
        (0x244e410, 0xb0, 0x1197014),
        (0x2492cf0, 0xa0, 0x1477984),
        (0x2492cf0, 0x208, 0x14242b0),
        (0x2492cf0, 0x238, 0x1424474),
        (0x2492cf0, 0x240, 0x142483c),
    ):
        if relocations.get(table+slot) != target:
            raise ValueError(f'Original draw vtable differs at {table+slot:#x}')
        slots.append({'table': hex(table), 'slot': hex(slot), 'target': hex(target)})
    checks = (
        (0x12f66b8, 'ldr', 'x0, [x8, #0x120]'),
        (0x12f66c0, 'ldr', 'x8, [x8, #0x10]'),
        (0x12f66c4, 'blr', 'x8'),
        (0x113048c, 'bl', '#0x315d18'),
        (0x315d44, 'ldr', 'x8, [x8, #0xa0]'),
        (0x315da4, 'blr', 'x8'),
        (0x14779fc, 'ldr', 'x5, [x10, #0x238]'),
        (0x1477a04, 'br', 'x5'),
        (0x1130450, 'bl', '#0x1478180'),
        (0x14781b8, 'ldr', 'x5, [x9, #0x238]'),
        (0x14781bc, 'br', 'x5'),
        (0x14247a0, 'bl', '#0x143ad38'),
        (0x14247b4, 'bl', '#0x143ab50'),
        (0x1197014, 'ret', ''),
    )
    instructions = []
    for at, mnemonic, operands in checks:
        instruction = next(image.disassembler.disasm(image.read(at, 4), at))
        if (instruction.mnemonic, instruction.op_str) != (mnemonic, operands):
            raise ValueError(f'Original draw instruction differs at {at:#x}: {instruction}')
        instructions.append({'address': hex(at), 'mnemonic': mnemonic, 'operands': operands,
                             'originalBytes': image.read(at, 4).hex()})
    api_calls = []
    for address in (0x143ab50, 0x143ad38, 0x143ae7c, 0x14a7eb8, 0x14f1890, 0x150039c):
        routine, _ = image.routine(address)
        for instruction in image.disassembler.disasm(image.read(address, routine['size']), address):
            if instruction.mnemonic in ('bl', 'b') and instruction.op_str.startswith('#'):
                target = int(instruction.op_str[1:], 16)
                imported = image.imports.get(target, '')
                if imported.startswith('glDraw') or imported == 'eglSwapBuffers':
                    api_calls.append({'function': hex(address), 'at': hex(instruction.address),
                                      'plt': hex(target), 'import': imported})
    required = {'glDrawElements', 'glDrawArrays', 'glDrawElementsInstanced',
                'glDrawArraysInstanced', 'eglSwapBuffers'}
    if {row['import'] for row in api_calls} != required:
        raise ValueError('Original graphics imports do not match recorded draw branches')
    return {'nativeSHA256': NATIVE_SHA256, 'vtableSlots': slots,
            'instructionChecks': instructions, 'apiCalls': api_calls,
            'scope': 'conditional static edges; no live driver, material, geometry or rendered frame supplied',
            'staticMeshB0IsNoop': True, 'renderedFrameObserved': False}


def prepare(native, output):
    raw = native.read_bytes()
    image = NativeImage(raw)
    output.mkdir(parents=True, exist_ok=True)
    imported = output/'input/libOrderChaos2.so'
    imported.parent.mkdir(parents=True, exist_ok=True)
    if imported.exists() and imported.read_bytes() != raw:
        raise ValueError('Existing import copy differs; preserve it for review')
    if not imported.exists():
        imported.write_bytes(raw)
    anchors = []
    for stage, entries in GROUPS.items():
        for address, role in entries.items():
            routine, _ = image.routine(address)
            if routine['start'] != hex(address):
                raise ValueError(f'Anchor is not an original function entry: {address:#x}')
            size = routine['size']
            anchors.append({'address': f'{address:08x}', 'researchLabel': 'oc2r_'+role,
                            'stage': stage, 'unwindBytes': size,
                            'originalFunctionSHA256': hashlib.sha256(image.read(address, size)).hexdigest()})
    manifest = {'manifestID': str(uuid.uuid4()), 'nativeSHA256': NATIVE_SHA256, 'inputBytes': len(raw),
                'originalUnwindEntries': len(image.starts), 'researchLabelsNotOriginalNames': True,
                'anchors': anchors}
    path = output/'manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    (output/'draw-evidence.json').write_text(json.dumps(draw_evidence(image), indent=2)+'\n')
    return imported, path


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('mode', choices=('prepare', 'import', 'export'))
    cli.add_argument('--native', type=Path, default=ROOT/'analysis/raw/beff-native/library.so')
    cli.add_argument('--output', type=Path, default=ROOT/'analysis/raw/ghidra-20261110')
    cli.add_argument('--project-dir', type=Path, default=ROOT/'analysis/raw/ghidra-projects')
    cli.add_argument('--project', default='OC2_31320_ARM64')
    cli.add_argument('--ghidra', type=Path, default=Path.home()/'Applications/OC2Tools/ghidra_12.2_PUBLIC')
    cli.add_argument('--jdk', type=Path, default=Path.home()/'Applications/OC2Tools/jdk-25.0.5+8/Contents/Home')
    args = cli.parse_args()
    for path in (args.output, args.project_dir):
        if not path.resolve().is_relative_to((ROOT/'analysis/raw').resolve()):
            cli.error('Original binary/project/decompilation stays in ignored analysis/raw/')
    imported, manifest = prepare(args.native, args.output)
    if args.mode == 'prepare':
        print(manifest)
        return
    args.project_dir.mkdir(parents=True, exist_ok=True)
    command = [str(args.ghidra/'support/analyzeHeadless'), str(args.project_dir), args.project]
    if args.mode == 'import':
        if (args.project_dir/(args.project+'.gpr')).exists():
            cli.error('Project exists; use export to preserve the current analysis')
        command += ['-import', str(imported), '-loader-imagebase', '0',
                    '-analysisTimeoutPerFile', '900', '-max-cpu', '4']
    else:
        command += ['-process', imported.name, '-noanalysis']
    command += ['-scriptPath', str(ROOT/'tools/ghidra'), '-postScript', 'OC2MapFlow.java',
                str(manifest), str(args.output), '-log', str(args.output/'headless.log'),
                '-scriptlog', str(args.output/'script.log')]
    env = dict(os.environ, JAVA_HOME=str(args.jdk), GHIDRA_HEADLESS_MAXMEM='12G')
    print('Launching original-ELF Ghidra analysis; full output stays local.', flush=True)
    subprocess.run(command, env=env, check=True)
    report = json.loads((args.output/'ghidra-report.json').read_text())
    manifest_data = json.loads(manifest.read_text())
    if report.get('manifestID') != manifest_data['manifestID']:
        raise ValueError('Ghidra did not produce a fresh export for this invocation; inspect script.log')
    manifest_data = manifest_data['anchors']
    if report['nativeSHA256'] != NATIVE_SHA256 or report['anchorCount'] != len(manifest_data):
        raise ValueError('Ghidra export is absent or does not match the current manifest')
    expected = {row['address'] for row in manifest_data}
    if {row['address'] for row in report['anchors']} != expected:
        raise ValueError('Ghidra export anchor set differs from current manifest')
    print(f"Saved Ghidra project; decompiled {report['decompiledAnchorCount']}/{report['anchorCount']} anchors.")


if __name__ == '__main__':
    main()
