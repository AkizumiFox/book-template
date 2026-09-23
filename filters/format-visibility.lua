--[[
Format Visibility Filter
========================
Strips content marked for specific output formats.
- when-format="html": show only in HTML (strip for LaTeX/PDF)
- when-format="pdf" or when-format="latex": show only in LaTeX/PDF (strip for HTML)
]]

local FORMAT = FORMAT or ""
local is_latex = FORMAT:match("latex") or FORMAT:match("pdf") or FORMAT:match("beamer")
local is_html = FORMAT:match("html")

local function get_when_format(div)
    if not div.attr or not div.attr.attributes then return nil end
    return div.attr.attributes["when-format"]
end

local function strip_div(div)
    local when = get_when_format(div)
    if not when then return nil end
    when = when:lower()
    if when == "html" and is_latex then
        return {}  -- Remove: return empty block list
    end
    if (when == "pdf" or when == "latex") and is_html then
        return {}
    end
    return nil  -- Keep
end

return {
    { Div = strip_div }
}
