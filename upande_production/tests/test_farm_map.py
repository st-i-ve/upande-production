import frappe
from frappe.tests.utils import FrappeTestCase


class TestFarmMapGeometry(FrappeTestCase):
    def test_bed_geometry_reads_upande_cores_zone_field_name(self):
        """upande_core's Zone calls the geometry field `geojson`; upande_scp's
        older one calls it `raw_geojson`. bed_geometry() must work with
        whichever one this site actually has."""
        from upande_production import farm_map

        if not frappe.db.table_exists("Zone"):
            self.skipTest("Zone doctype not installed on this site")
        field = "geojson" if frappe.get_meta("Zone").has_field("geojson") else "raw_geojson"

        house = make_warehouse("TEST GH ZONEMAP")
        bed_name = f"{house} - Bed 99"
        if frappe.db.exists("Bed", bed_name):
            frappe.delete_doc("Bed", bed_name, force=True, ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Bed", "greenhouse": house, "unit_type": "Bed", "bed": 99,
            "bed_length": 30, "bed_width": 1,
        }).insert(ignore_permissions=True)

        import json as _json
        geojson = _json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"fid": 1, "line_id": 504, "segment_id": 1, "zone_id": 1},
                "geometry": {"type": "LineString", "coordinates": [[35.757, 0.0554], [35.7571, 0.0553]]},
            }],
        })
        zone_name = f"{bed_name} - Zone 1"
        if frappe.db.exists("Zone", zone_name):
            frappe.delete_doc("Zone", zone_name, force=True, ignore_permissions=True)
        frappe.get_doc({
            "doctype": "Zone", "bed": bed_name, "zone": 1, **{field: geojson},
        }).insert(ignore_permissions=True)

        r = farm_map.bed_geometry(house)
        self.assertEqual(r["source"], "zones")
        self.assertEqual(len(r["rows"]), 1)
        self.assertEqual(r["rows"][0]["bed"], 504)
        self.assertEqual(len(r["rows"][0]["coords"]), 2)

    def test_house_strips_prefix_and_company(self):
        from upande_production import farm_map
        for raw, want in [("Main GH 02 - TFC", "GH 02"), ("Main GH 21 - MFL", "GH 21"),
                          ("GH04 - KR", "GH04"), ("Block K1 - TFC", "Block K1")]:
            self.assertEqual(farm_map.house(raw), want)

    def test_ring_area_matches_a_known_rectangle(self):
        # ~100 m east-west by ~100 m north-south on the equator.
        from upande_production import farm_map
        d = 100 / 111_320.0
        ring = [[0, 0], [d, 0], [d, d], [0, d], [0, 0]]
        self.assertAlmostEqual(farm_map._ring_area_m2(ring), 10_000, delta=50)

    def test_ring_area_ignores_degenerate_rings(self):
        from upande_production import farm_map
        self.assertEqual(farm_map._ring_area_m2([[0, 0], [1, 1]]), 0.0)

    def test_polygons_survive_a_double_encoded_field(self):
        import json
        from upande_production import farm_map
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Polygon",
                                             "coordinates": [[[1, 2], [3, 4], [5, 6], [1, 2]]]}}]}
        inner = json.dumps(fc)
        self.assertEqual(len(farm_map._polygons_from_geojson(inner)), 1)
        # a value that was JSON-encoded a second time on the way into the field
        self.assertEqual(len(farm_map._polygons_from_geojson(json.dumps(inner))), 1)

    def test_polygons_skip_non_polygon_geometry(self):
        from upande_production import farm_map
        fc = {"features": [{"geometry": {"type": "LineString", "coordinates": [[1, 2], [3, 4]]}}]}
        self.assertEqual(farm_map._polygons_from_geojson(fc), [])
        self.assertEqual(farm_map._polygons_from_geojson(None), [])
        self.assertEqual(farm_map._polygons_from_geojson("not json"), [])

    def test_bundled_survey_is_present_and_well_formed(self):
        from upande_production import farm_map
        geom = farm_map._bundled_geometry()
        self.assertTrue(geom, "bundled greenhouse geometry is missing")
        for name, polys in geom.items():
            for poly in polys:
                for ring in poly:
                    self.assertGreaterEqual(len(ring), 4, f"{name} ring is not closeable")
                    for lon, lat in ring:
                        # Kenya: the survey must not have been written [lat, lon].
                        self.assertTrue(30 < lon < 42, f"{name} longitude {lon} out of range")
                        self.assertTrue(-5 < lat < 5, f"{name} latitude {lat} out of range")
