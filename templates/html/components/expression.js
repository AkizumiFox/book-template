/**
 * Expression parser for plots. Same grammar as the parser in filters/components.lua,
 * which turns the same expressions into pgfplots for the PDF:
 *
 *   numbers, x, parameters, pi, e, + - * / ^ (right-associative), unary minus,
 *   parentheses, and sin cos tan asin acos atan sinh cosh tanh exp log sqrt abs
 *   (log is the natural logarithm).
 */

const FUNCTIONS = {
    sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
    sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh, exp: Math.exp, log: Math.log,
    sqrt: Math.sqrt, abs: Math.abs,
};
const CONSTANTS = { pi: Math.PI, e: Math.E };

function tokenize(text) {
    const tokens = [];
    const pattern = /\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|([A-Za-z_]\w*)|([-+*/^()]))/y;
    let index = 0;
    while (index < text.length) {
        if (/^\s*$/.test(text.slice(index))) break;
        pattern.lastIndex = index;
        const match = pattern.exec(text);
        if (!match) throw new Error(`unexpected character '${text.slice(index).trim()[0]}'`);
        if (match[1] !== undefined) tokens.push({ kind: 'num', value: parseFloat(match[1]) });
        else if (match[2] !== undefined) tokens.push({ kind: 'name', value: match[2] });
        else tokens.push({ kind: match[3] });
        index = pattern.lastIndex;
    }
    return tokens;
}

/**
 * Compile an expression into a function of a scope object ({x, a, ...}).
 * `variables` lists the allowed parameter names besides x.
 */
export function compile(text, variables = []) {
    const tokens = tokenize(text);
    const allowed = new Set(['x', ...variables]);
    let pos = 0;
    const peek = () => tokens[pos] && tokens[pos].kind;
    // An operand directly after another (2x, x(x+1)) is a missing multiplication sign
    const missingOperator = () => {
        const token = tokens[pos];
        if (token && (token.kind === 'num' || token.kind === 'name' || token.kind === '(')) {
            throw new Error(`missing '*' before '${token.value ?? token.kind}'`);
        }
    };
    const take = kind => {
        if (peek() !== kind) { missingOperator(); throw new Error(`expected '${kind}'`); }
        return tokens[pos++];
    };

    function primary() {
        const token = tokens[pos];
        if (!token) throw new Error('unexpected end of expression');
        if (token.kind === 'num') { pos++; return () => token.value; }
        if (token.kind === '(') { pos++; const inner = expr(); take(')'); return inner; }
        if (token.kind === 'name') {
            pos++;
            if (peek() === '(') {
                const fn = FUNCTIONS[token.value];
                if (!fn) throw new Error(`unknown function '${token.value}'`);
                take('('); const arg = expr(); take(')');
                return scope => fn(arg(scope));
            }
            if (allowed.has(token.value)) return scope => scope[token.value];
            if (token.value in CONSTANTS) { const value = CONSTANTS[token.value]; return () => value; }
            throw new Error(`unknown name '${token.value}'`);
        }
        throw new Error(`unexpected '${token.kind}'`);
    }
    function power() {
        const base = primary();
        if (peek() === '^') { pos++; const exponent = unary(); return scope => Math.pow(base(scope), exponent(scope)); }
        return base;
    }
    function unary() {
        if (peek() === '-') { pos++; const operand = unary(); return scope => -operand(scope); }
        return power();
    }
    function term() {
        let left = unary();
        while (peek() === '*' || peek() === '/') {
            const op = tokens[pos++].kind, a = left, b = unary();
            left = op === '*' ? scope => a(scope) * b(scope) : scope => a(scope) / b(scope);
        }
        return left;
    }
    function expr() {
        let left = term();
        while (peek() === '+' || peek() === '-') {
            const op = tokens[pos++].kind, a = left, b = term();
            left = op === '+' ? scope => a(scope) + b(scope) : scope => a(scope) - b(scope);
        }
        return left;
    }

    const result = expr();
    if (pos < tokens.length) {
        missingOperator();
        const token = tokens[pos];
        throw new Error(`unexpected '${token.value ?? token.kind}'`);
    }
    return result;
}

/** "a=1:0..3, b=0.5:-1..1" -> [{name, value, min, max}] */
export function parseParams(text) {
    if (!text || !text.trim()) return [];
    return text.split(',').map(item => {
        const match = item.match(/^\s*([A-Za-z_]\w*)\s*=\s*([-\d.eE]+)\s*:\s*([-\d.eE]+)\s*\.\.\s*([-\d.eE]+)\s*$/);
        if (!match) throw new Error(`bad parameter '${item.trim()}'`);
        return { name: match[1], value: parseFloat(match[2]), min: parseFloat(match[3]), max: parseFloat(match[4]) };
    });
}

/** "min,max" -> [min, max] */
export function parseRange(text) {
    const parts = (text || '').split(',').map(parseFloat);
    if (parts.length !== 2 || parts.some(Number.isNaN) || parts[0] >= parts[1]) return null;
    return parts;
}
