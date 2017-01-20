import math

# See https://github.com/SkyTruth/benthos-pipeline/blob/master/benthosp/projections.py#L44 for more details...

class TMSBbox(object):
    def __init__(self, zoom, x, y):
        self.zoom = zoom
        self.x = x
        self.y = y

    @classmethod
    def fromstring(cls, str):
        return cls(*[int(x) for x in str.split(",")])

    originShift = 2 * math.pi * 6378137 / 2.0
    initialResolution = 2 * math.pi * 6378137

    def to3857(self):
        res = self.initialResolution / (2**self.zoom)
        mx1 = self.x * res - self.originShift
        my1 = self.y * res - self.originShift

        mx2 = (self.x+1) * res - self.originShift
        my2 = (self.y+1) * res - self.originShift
        return {"left": mx1,
                "top": my1,
                "right": mx2,
                "bottom": my2}

