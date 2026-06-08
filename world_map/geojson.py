"""GeoJSON serialisation helpers."""


def point_feature(lat, lon, properties):
    return {
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [float(lon), float(lat)]},
        'properties': properties,
    }


def feature_collection(features):
    return {'type': 'FeatureCollection', 'features': features}
