from __future__ import print_function, division, absolute_import
from .flatten import InputContour, OutputContour
from .exceptions import (
    InvalidSubjectContourError, InvalidClippingContourError, ExecutionError)
import pyclipper


"""
General Suggestions:
- Contours should only be sent here if they actually overlap.
  This can be checked easily using contour bounds.
- Only perform operations on closed contours.
- contours must have an on curve point
- some kind of a log
"""


_operationMap = {
    "union": pyclipper.CT_UNION,
    "intersection": pyclipper.CT_INTERSECTION,
    "difference": pyclipper.CT_DIFFERENCE,
    "xor": pyclipper.CT_XOR,
}

_fillTypeMap = {
    "evenOdd": pyclipper.PFT_EVENODD,
    "nonZero": pyclipper.PFT_NONZERO,
    # we keep the misspelling for compatibility with earlier versions
    "noneZero": pyclipper.PFT_NONZERO,
}


def _addContour(clipperPath, contour, fillType, contourCount):
    if pyclipper.Area(contour) == 0:
        # skip paths with no area,
        # BUT self intersecting paths could have no area...
        dummy = pyclipper.Pyclipper()
        try:
            dummy.AddPath(contour, fillType)
            shouldBeAValidPath = True
        except pyclipper.ClipperException:
            shouldBeAValidPath = False
        if not shouldBeAValidPath:
            return

    try:
        clipperPath.AddPath(contour, fillType)
    except pyclipper.ClipperException:
        raise InvalidSubjectContourError("contour %d is invalid for clipping" % contourCount)


def clipExecute(subjectContours, clipContours, operation, subjectFillType="nonZero",
                clipFillType="nonZero"):
    pc = pyclipper.Pyclipper()

    for i, subjectContour in enumerate(subjectContours):
        _addContour(clipperPath=pc, contour=subjectContour, fillType=pyclipper.PT_SUBJECT, contourCount=i)

    for j, clipContour in enumerate(clipContours):
        _addContour(clipperPath=pc, contour=clipContour, fillType=pyclipper.PT_CLIP, contourCount=i)

    bounds = pc.GetBounds()
    if (bounds.bottom, bounds.left, bounds.top, bounds.right) == (0, 0, 0, 0):
        # do nothing if there are no paths
        return []

    try:
        solution = pc.Execute(_operationMap[operation],
                              _fillTypeMap[subjectFillType],
                              _fillTypeMap[clipFillType])
    except pyclipper.ClipperException as exc:
        raise ExecutionError(exc)

    return [[tuple(p) for p in path] for path in solution]


def _performOperation(operation, subjectContours, clipContours, outPen):
    # prep the contours
    subjectInputContours = [InputContour(contour) for contour in subjectContours if contour and len(contour) > 1]
    clipInputContours = [InputContour(contour) for contour in clipContours if contour and len(contour) > 1]
    inputContours = subjectInputContours + clipInputContours

    resultContours = clipExecute([subjectInputContour.originalFlat for subjectInputContour in subjectInputContours],
                                 [clipInputContour.originalFlat for clipInputContour in clipInputContours],
                                 operation, subjectFillType="nonZero", clipFillType="nonZero")
    # convert to output contours
    outputContours = [OutputContour(contour) for contour in resultContours]
    # re-curve entire contour
    for inputContour in inputContours:
        for outputContour in outputContours:
            if outputContour.final:
                continue
            if outputContour.reCurveFromEntireInputContour(inputContour):
                # the input is expired if a match was made,
                # so stop passing it to the outputs
                break
    # curve fit
    for outputContour in outputContours:
        outputContour.reCurveSubSegments(inputContours)
    # output the results
    for outputContour in outputContours:
        outputContour.drawPoints(outPen)
    return outputContours


class BooleanOperationManager(object):

    @staticmethod
    def union(contours, outPen):
        return _performOperation("union", contours, [], outPen)

    @staticmethod
    def difference(subjectContours, clipContours, outPen):
        return _performOperation("difference", subjectContours, clipContours, outPen)

    @staticmethod
    def intersection(subjectContours, clipContours, outPen):
        return _performOperation("intersection", subjectContours, clipContours, outPen)

    @staticmethod
    def xor(subjectContours, clipContours, outPen):
        return _performOperation("xor", subjectContours, clipContours, outPen)

    @staticmethod
    def getIntersections(contours):
        from .flatten import _scalePoints, inverseClipperScale
        # prep the contours
        inputContours = [InputContour(contour) for contour in contours if contour and len(contour) > 1]

        inputFlatPoints = set()
        for contour in inputContours:
            inputFlatPoints.update(contour.originalFlat)

        resultContours = clipExecute(
            [inputContour.originalFlat for inputContour in inputContours], [],
            "union", subjectFillType="nonZero", clipFillType="nonZero")

        resultFlatPoints = set()
        for contour in resultContours:
            resultFlatPoints.update(contour)

        intersections = resultFlatPoints - inputFlatPoints
        return _scalePoints(intersections, inverseClipperScale)
