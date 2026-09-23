/**
 * Interactive components loader.
 *
 * Included only on pages that use a component (filters/components.lua sets
 * has-components). Each component's module is imported only if the page has one.
 */

const version = new URL(import.meta.url).search;  // "?v=<asset hash>", reused for the modules

function load(name) {
    return import(new URL(`components/${name}.js${version}`, import.meta.url));
}

const COMPONENTS = [
    ['.code-cell', 'cell'],
    ['.plot', 'plot'],
    ['.widget', 'widget'],
];

for (const [selector, name] of COMPONENTS) {
    const elements = document.querySelectorAll(selector);
    if (elements.length) {
        load(name)
            .then(module => module.init([...elements], { version }))
            .catch(error => console.error(`Could not load ${name} component:`, error));
    }
}
