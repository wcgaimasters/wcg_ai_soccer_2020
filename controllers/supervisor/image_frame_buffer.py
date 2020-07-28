#!/usr/bin/env python3

import base64


class ImageFrameBuffer:
    def __init__(self, camera, nx, ny):
        self.camera = camera
        self.width = self.camera.getWidth()
        self.height = self.camera.getHeight()
        self.subImageWidth = nx
        self.subImageHeight = ny
        self.reset()

    def reset(self):
        self.oldImage = None
        self.currentImage = None
        self.lastUpdateTime = None

    def update_image(self, time):
        ret = []
        if self.lastUpdateTime is not None and time - self.lastUpdateTime <= 0.001 * self.camera.getSamplingPeriod():
            return ret
        self.lastUpdateTime = time
        if self.currentImage is not None:
            self.oldImage = self.currentImage
        self.currentImage = self.camera.getImage()
        xDiv = int(self.width / self.subImageWidth)
        yDiv = int(self.height / self.subImageHeight)
        # Loop through sub-images
        for y in range(self.subImageWidth):
            yStart = y * yDiv
            yEnd = min(yStart + yDiv, self.height)
            yLength = yEnd - yStart
            for x in range(self.subImageHeight):
                xStart = x * xDiv
                xEnd = min(xStart + xDiv, self.width)
                xLength = xEnd - xStart
                changed = False
                # loop through sub-image pixels
                for py in range(yStart, yEnd):
                    index = 4 * (py * self.width + xStart)
                    if self.oldImage is None or self.oldImage[index:index + xLength * 4] != self.currentImage[index:index + xLength * 4]:
                        changed = True
                        break
                if changed:
                    pixels = []
                    for py in range(yStart, yEnd):
                        index = 4 * (py * self.width + xStart)
                        pixels.extend(self.currentImage[index:index + xLength * 4])
                    ret.append([xStart, yStart, xLength, yLength, base64.b64encode(bytes(pixels)).decode()])
        return ret
