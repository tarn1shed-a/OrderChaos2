"""Host storage for one serial native RPC owner, never shared native state.

Every body still validates its own input bytes and constructs its own Uc,
globals, heap, world, controller, queue and compositor. Only the immutable ELF
inspection object is reused. ELFFile's stream belongs to this serial owner.
"""
import hashlib
import threading


class SourceRuntimeResources:
    def __init__(self):
        self._thread = threading.get_ident()
        self._images = {}

    def native_image(self, raw, constructor):
        if threading.get_ident() != self._thread:
            raise ValueError('Native inspection resources require their serial RPC owner')
        if type(raw) is not bytes or not callable(constructor):
            raise ValueError('Verified original image bytes and constructor required')
        key = (constructor, hashlib.sha256(raw).digest())
        image = self._images.get(key)
        if image is None:
            image = constructor(raw)
            if type(image.data) is not bytes or image.data != raw:
                raise ValueError('Native image constructor changed its verified bytes')
            self._images[key] = image
        elif image.data != raw:
            raise ValueError('Original native image bytes differ')
        return image

    def native_image_file(self, root, descriptor, constructor):
        """Same immutable image, after a fresh streamed source validation.

        No source-buffer mmap is used for ELF parsing. The first image keeps
        its original bytes; subsequent bodies do not allocate another full
        file-sized bytes temporary. Writable Uc state remains caller-owned.
        """
        if threading.get_ident() != self._thread:
            raise ValueError('Native inspection resources require their serial RPC owner')
        if not callable(constructor):
            raise ValueError('Verified original image constructor required')
        from source_immutable_inputs import verify_source, native_elf_file_enabled, require_native_program
        program_file = native_elf_file_enabled()
        path, digest, size = verify_source(root, descriptor)
        sources = getattr(self, '_image_file_sources', None)
        if sources is None:
            sources = self._image_file_sources = {}
        identity = (constructor, path)
        previous = sources.get(identity)
        if previous is not None and previous != (digest, size):
            raise ValueError('Original native image source identity changed')
        image = self._images.get((constructor, bytes.fromhex(digest)))
        if image is None:
            if program_file:
                image = constructor.from_file(root, descriptor)
                try:
                    proof = require_native_program(image.data, image.elf.stream)
                    if proof.sha256 != digest or proof.size != size:
                        raise ValueError('Original program file identity differs')
                except BaseException:
                    image.elf.close()
                    raise
                self._images[(constructor, bytes.fromhex(digest))] = image
            else:
                raw = path.read_bytes()
                if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                    raise ValueError('Original native image changed after stream validation')
                image = self.native_image(raw, constructor)
        elif program_file:
            proof = require_native_program(image.data, image.elf.stream)
            if proof.sha256 != digest or proof.size != size or hashlib.sha256(image.data).hexdigest() != digest:
                raise ValueError('Retained authenticated native program differs')
        elif (type(image.data) is not bytes or len(image.data) != size or
              hashlib.sha256(image.data).hexdigest() != digest):
            raise ValueError('Retained immutable native image differs')
        sources[identity] = (digest, size)
        return image

    def retain_compositor(self, vm):
        if threading.get_ident() != self._thread:
            raise ValueError('Compositor retention requires its serial RPC owner')
        if getattr(vm, 'batch_prepared', False) is not True or not getattr(vm, 'bound_motion', None):
            raise ValueError('Retain data only after original preparation and binding')
        # These are the only self.data fields read by the four runtime
        # compose_values consumers. Native geometry/masks/tracks/buffers have
        # already been built and validated; no native storage is discarded.
        skins = vm.data['rig']['skins']
        retained = tuple({'boneNames': tuple(skin['boneNames'])} for skin in skins)
        if not retained or any(not all(isinstance(name, str) for name in skin['boneNames'])
                               for skin in retained):
            raise ValueError('Original compositor bone-name table required')
        vm.data = {'rig': {'skins': retained}}
