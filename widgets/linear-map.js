/**
 * Linear map of the plane.
 *
 *     ::: {.widget src="widgets/linear-map.js" matrix="2,1,0,1"}
 *     ::: {.print}
 *     ...static figure or description for the PDF...
 *     :::
 *     :::
 *
 * Shows the unit square and its image under the matrix [[a, b], [c, d]] (given row by
 * row). Drag the images of e1 and e2 to change the matrix. Options:
 *   matrix="a,b,c,d"       initial matrix (default: identity)
 *   extent="3"             half-width of the visible square; by default the view is fitted
 *                          to the image of the unit square, so nothing is cut off
 *   determinant="false"    hide the signed area of the image
 *   readout="area"         call the number "signed area" instead of "det A", for chapters
 *                          before the determinant is defined
 */

function parseMatrix(text) {
    const values = (text || '1,0,0,1').split(',').map(Number);
    return values.length === 4 && values.every(Number.isFinite) ? values : [1, 0, 0, 1];
}

const round = v => Math.round(v * 100) / 100;

export default async function mount(element, options, { loadJSXGraph, ensureId, COLORS }) {
    const JXG = await loadJSXGraph();
    const [a, b, c, d] = parseMatrix(options.matrix);
    // Fit the view to the image of the unit square (and the square itself), with a margin.
    // The box is square, because the board keeps the aspect ratio, and is centred on the
    // picture rather than on the origin, so no part is cut off and little space is wasted.
    const xs = [0, 1, a, b, a + b], ys = [0, 1, c, d, c + d];
    const fixed = Number(options.extent);
    const pad = 1;
    let [left, right] = [Math.min(...xs) - pad, Math.max(...xs) + pad];
    let [bottom, top] = [Math.min(...ys) - pad, Math.max(...ys) + pad];
    const side = Math.max(3, right - left, top - bottom);
    const centre = [(left + right) / 2, (bottom + top) / 2];
    const box = fixed
        ? [-fixed, fixed, fixed, -fixed]
        : [centre[0] - side / 2, centre[1] + side / 2, centre[0] + side / 2, centre[1] - side / 2];

    const boardElement = document.createElement('div');
    boardElement.className = 'widget-board';
    const readout = document.createElement('div');
    readout.className = 'widget-readout';
    element.append(boardElement, readout);

    const board = JXG.JSXGraph.initBoard(ensureId(boardElement), {
        boundingbox: box,
        axis: true, keepAspectRatio: true, showCopyright: false, showNavigation: false,
        pan: { enabled: false }, zoom: { enabled: false },
    });

    // Unit square, faint
    board.create('polygon', [[0, 0], [1, 0], [1, 1], [0, 1]], {
        fillColor: '#999', fillOpacity: 0.1, borders: { strokeColor: '#999', dash: 2 }, vertices: { visible: false },
        fixed: true, highlight: false,
    });

    // Images of the standard basis vectors: the columns (a, c) and (b, d)
    const snap = { snapToGrid: true, snapSizeX: 0.25, snapSizeY: 0.25 };
    const e1 = board.create('point', [a, c], { name: 'Te₁', color: COLORS[0], size: 4, ...snap });
    const e2 = board.create('point', [b, d], { name: 'Te₂', color: COLORS[1], size: 4, ...snap });
    const origin = [0, 0];
    board.create('arrow', [origin, e1], { strokeColor: COLORS[0], strokeWidth: 3, fixed: true });
    board.create('arrow', [origin, e2], { strokeColor: COLORS[1], strokeWidth: 3, fixed: true });
    const corner = board.create('point', [() => e1.X() + e2.X(), () => e1.Y() + e2.Y()], { visible: false });
    board.create('polygon', [origin, e1, corner, e2], {
        fillColor: COLORS[2], fillOpacity: 0.2, borders: { strokeColor: COLORS[2] }, vertices: { visible: false },
        highlight: false, hasInnerPoints: false,
    });

    const showDeterminant = options.determinant !== 'false';
    const areaWording = options.readout === 'area';

    // The readout is a real 2-by-2 array with brackets, not a line of ASCII
    const matrixBox = document.createElement('span');
    matrixBox.className = 'widget-matrix';
    const name = document.createElement('span');
    name.className = 'widget-matrix-name';
    name.textContent = 'A';
    const grid = document.createElement('span');
    grid.className = 'widget-matrix-grid';
    const cells = [0, 1, 2, 3].map(() => {
        const cell = document.createElement('span');
        cell.className = 'widget-matrix-cell';
        grid.append(cell);
        return cell;
    });
    matrixBox.append(name, document.createTextNode(' = '), grid);
    const value = document.createElement('span');
    value.className = 'widget-value';
    readout.append(matrixBox, value);

    const update = () => {
        const [m11, m21, m12, m22] = [e1.X(), e1.Y(), e2.X(), e2.Y()].map(round);
        [m11, m12, m21, m22].forEach((entry, i) => { cells[i].textContent = String(entry); });
        const number = round(m11 * m22 - m12 * m21);
        value.replaceChildren();
        if (!showDeterminant) return;
        if (areaWording) {
            value.append(`signed area = ${number}`);
        } else {
            const bold = document.createElement('strong');
            bold.textContent = 'A';
            value.append('det ', bold, ` = ${number}`);
        }
    };
    board.on('update', update);
    update();
}
