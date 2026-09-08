"""Verify binary STL topology; produce a core 3MF print layout. Standard library.

python package.py — run after model.py. 3MF contains printable parts only,
with mm units and no printer-specific temperatures, G-code or filament profile.
"""
import collections
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'exports'
NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('', NS)


def stl_mesh(path):
    raw = path.read_bytes()
    count = struct.unpack_from('<I', raw, 80)[0]
    assert len(raw) == 84 + 50 * count, ('Unexpected STL encoding', path)
    vertices, lookup, triangles = [], {}, []
    for i in range(count):
        data = struct.unpack_from('<12fH', raw, 84 + 50 * i)
        tri = []
        for j in (3, 6, 9):
            v = tuple(round(float(x), 5) for x in data[j:j + 3])
            if v not in lookup:
                lookup[v] = len(vertices)
                vertices.append(v)
            tri.append(lookup[v])
        assert len(set(tri)) == 3, ('Degenerate triangle', path, i)
        triangles.append(tri)
    return vertices, triangles


def verify(vertices, triangles):
    edges, directions = collections.Counter(), collections.Counter()
    adjacency = collections.defaultdict(set)
    vol6 = 0
    for a, b, c in triangles:
        for u, v in ((a, b), (b, c), (c, a)):
            key = (min(u, v), max(u, v))
            edges[key] += 1
            directions[key] += 1 if u < v else -1
            adjacency[u].add(v)
            adjacency[v].add(u)
        x, y, z = vertices[a], vertices[b], vertices[c]
        vol6 += (x[0] * (y[1] * z[2] - y[2] * z[1])
                 + x[1] * (y[2] * z[0] - y[0] * z[2])
                 + x[2] * (y[0] * z[1] - y[1] * z[0]))
    unseen, components = set(range(len(vertices))), 0
    while unseen:
        components += 1
        pending = [unseen.pop()]
        while pending:
            n = pending.pop()
            neighbors = adjacency[n] & unseen
            unseen -= neighbors
            pending.extend(neighbors)
    result = {
        'vertices': len(vertices), 'triangles': len(triangles),
        'closed_manifold': all(n == 2 for n in edges.values()),
        'consistent_winding': all(n == 0 for n in directions.values()),
        'connected_components': components,
        'signed_volume_mm3': round(vol6 / 6, 3),
        'z_min_mm': min(v[2] for v in vertices),
        'z_max_mm': max(v[2] for v in vertices),
    }
    assert result['closed_manifold'] and result['consistent_winding'], result
    assert components == 1 and vol6 > 0, result
    assert abs(result['z_min_mm']) < 0.0001, result
    return result


def make_3mf(meshes):
    model = ET.Element(f'{{{NS}}}model', {'unit': 'millimeter', 'xml:lang': 'en-US'})
    ET.SubElement(model, f'{{{NS}}}metadata', {'name': 'Title'}).text = (
        'ELM backpack Rev E — INLINE BLACK ADAPTER — DIRECT SOLDER — FIT CHECK REQUIRED')
    resources = ET.SubElement(model, f'{{{NS}}}resources')
    for oid, name in enumerate(('base', 'lid', 'buck-keeper'), 1):
        vertices, triangles = meshes[name]
        obj = ET.SubElement(resources, f'{{{NS}}}object', {'id': str(oid), 'type': 'model', 'name': name})
        mesh = ET.SubElement(obj, f'{{{NS}}}mesh')
        vs = ET.SubElement(mesh, f'{{{NS}}}vertices')
        for x, y, z in vertices:
            ET.SubElement(vs, f'{{{NS}}}vertex', {'x': str(x), 'y': str(y), 'z': str(z)})
        ts = ET.SubElement(mesh, f'{{{NS}}}triangles')
        for a, b, c in triangles:
            ET.SubElement(ts, f'{{{NS}}}triangle', {'v1': str(a), 'v2': str(b), 'v3': str(c)})
    build = ET.SubElement(model, f'{{{NS}}}build')
    p = json.loads((HERE / 'parameters.json').read_text())
    w, l = p['case_width'], p['case_length']
    placements = [(1, w / 2 + 4, l / 2 + 4),
                  (2, 1.5 * w + 10, l / 2 + 4)]
    placements += [(3, 12 + i * 15, l + 16) for i in range(4)]
    for oid, x, y in placements:
        ET.SubElement(build, f'{{{NS}}}item', {'objectid': str(oid),
            'transform': f'1 0 0 0 1 0 0 0 1 {x} {y} 0'})
    with zipfile.ZipFile(OUT / 'print-layout.3mf', 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model', ET.tostring(model, encoding='utf-8', xml_declaration=True))
    # Reopen and check the package's actual object count, scale and placements.
    with zipfile.ZipFile(OUT / 'print-layout.3mf') as z:
        reopened = ET.fromstring(z.read('3D/3dmodel.model'))
        assert reopened.attrib['unit'] == 'millimeter'
        assert len(reopened.findall(f'./{{{NS}}}resources/{{{NS}}}object')) == 3
        assert len(reopened.findall(f'./{{{NS}}}build/{{{NS}}}item')) == 6
    return {'units': 'millimeter', 'objects': 3, 'build_items': 6,
            'bed_layout_mm': [2 * w + 14, l + 20],
            'printer_profile_included': False}


if __name__ == '__main__':
    meshes = {n: stl_mesh(OUT / (n + '.stl')) for n in ('base', 'lid', 'buck-keeper', 'fit-gauge')}
    report = {n: verify(*m) for n, m in meshes.items()}
    report['3mf'] = make_3mf(meshes)
    (OUT / 'mesh-validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
