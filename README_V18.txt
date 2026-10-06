ECG LABEL TOOL v18 — FREE CANVAS

Main change from v17:
- The drag designer is now a FREE CANVAS.
- Nominal paper size is shown only as a gray reference box in the designer.
- Virtual Print Area is shown only as a green visual guide.
- Neither the nominal paper box nor Virtual Print Area blocks dragging.
- Elements can be dragged beyond those boxes and can use negative coordinates.
- Virtual Print Area NEVER clips PDF, RAW/driver output, or preview rendering.
- Printer calibration offset/skew is kept separate from designer coordinates.

Recommended workflow:
1. Open / Apply JSON.
2. Open Drag Designer.
3. Set Virtual Print Area only as a visual approximation of the real tag face.
4. Drag elements freely until the physical print is correct.
5. Save JSON when satisfied.
6. Use Calibration separately for printer/mechanical offset.

Important:
Physical printer/driver behavior can still cut content according to the actual media and driver page size. v18 intentionally does not pretend the virtual guide is a guaranteed hardware boundary.
