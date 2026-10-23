"""Read WDDM resident shared GPU memory from WSL, in a separate process.

ABI: Microsoft DirectX-Headers dxcore_interface.h and WinSDK d3dkmthk.h.
No CUDA context, allocations, driver changes, Windows executable or SSH.
"""
import ctypes as c
import json
import struct
import uuid

V, U, H, S = c.c_void_p, c.c_uint32, c.c_int32, c.c_size_t


def guid(text):
    return (c.c_ubyte * 16).from_buffer_copy(uuid.UUID(text).bytes_le)


def method(pointer, slot, result, *arguments):
    table = c.cast(pointer, c.POINTER(c.POINTER(V))).contents
    return c.CFUNCTYPE(result, V, *arguments)(table[slot])


def check(status):
    if status < 0:
        raise OSError(f'DXCore query failed: 0x{status & 0xffffffff:08x}')


def release(pointer):
    if pointer:
        method(pointer, 2, U)(pointer)


def shared_segments(rows):
    """WDDM aperture segments are resident GPU-accessible system memory."""
    return sum(resident for resident, aperture in rows if aperture)


def snapshot():
    library = c.CDLL('/usr/lib/wsl/lib/libdxcore.so')
    library.DXCoreCreateAdapterFactory.argtypes = [V, c.POINTER(V)]
    library.DXCoreCreateAdapterFactory.restype = H
    library.D3DKMTQueryStatistics.argtypes = [V]
    library.D3DKMTQueryStatistics.restype = H
    factory, listing = V(), V()
    output = []
    try:
        check(library.DXCoreCreateAdapterFactory(guid('78ee5945-c36e-4b13-a669-005dd11c0f06'), c.byref(factory)))
        check(method(factory, 3, H, U, V, V, c.POINTER(V))(factory, 1,
            guid('248e2800-a793-4724-abaa-23a6de1be090'),
            guid('526c7776-40e9-459b-b711-f32ad76dfc28'), c.byref(listing)))
        count = method(listing, 4, U)(listing)
        for index in range(min(count, 32)):
            adapter = V()
            try:
                check(method(listing, 3, H, U, V, c.POINTER(V))(listing, index,
                    guid('f0db4c7f-fe5a-42a2-bd62-f2a6cf6fc83e'), c.byref(adapter)))
                size = S()
                check(method(adapter, 7, H, U, c.POINTER(S))(adapter, 2, c.byref(size)))
                if not 0 < size.value <= 4096:
                    continue
                name = c.create_string_buffer(size.value)
                check(method(adapter, 6, H, U, S, V)(adapter, 2, size.value, name))
                capacity = c.c_uint64()
                check(method(adapter, 6, H, U, S, V)(adapter, 9, 8, c.byref(capacity)))
                luid = (c.c_ubyte * 8)()
                check(method(adapter, 6, H, U, S, V)(adapter, 0, 8, luid))
                # Win64 D3DKMT_QUERYSTATISTICS is 0x328 bytes. Type/LUID are at
                # 0/4, result at 24, segment query at 0x320. WSL uses this ABI.
                query = c.create_string_buffer(0x328)
                query[4:12] = bytes(luid)
                check(library.D3DKMTQueryStatistics(query))
                segments = struct.unpack_from('<I', query.raw, 24)[0]
                if not 0 < segments <= 32:
                    continue
                rows = []
                for segment in range(segments):
                    query = c.create_string_buffer(0x328)
                    struct.pack_into('<I', query, 0, 3)  # SEGMENT
                    query[4:12] = bytes(luid)
                    struct.pack_into('<I', query, 0x320, segment)
                    check(library.D3DKMTQueryStatistics(query))
                    resident = struct.unpack_from('<Q', query.raw, 40)[0]
                    aperture = struct.unpack_from('<I', query.raw, 64)[0]
                    if aperture not in (0, 1):
                        raise ValueError('Unexpected WDDM segment flags')
                    rows.append((resident, aperture))
                output.append({'name': name.value.decode('utf-8', 'replace'),
                    'shared_memory_used': shared_segments(rows),
                    'shared_memory_total': capacity.value,
                    'shared_memory_source': 'wsl_wddm_resident_segments'})
            except (OSError, ValueError):
                continue
            finally:
                release(adapter)
    finally:
        release(listing)
        release(factory)
    return output


if __name__ == '__main__':
    try:
        print(json.dumps(snapshot()))
    except (OSError, AttributeError, ValueError):
        print('[]')
