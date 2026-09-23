--[[
Labeled Lists Filter
====================
Handles enumitem-style labels on ordered lists:

    ::: {.enumerate options="label=(VS\arabic*)"}
    1. ...
    :::

LaTeX: \begin{enumerate}[label=(VS\arabic*)] ... \end{enumerate}
HTML:  <ol class="labeled-list"> with an explicit label span in each item.
]]

local COUNTER_STYLES = {
    arabic = function(n) return tostring(n) end,
    alph = function(n) return string.char(96 + n) end,
    Alph = function(n) return string.char(64 + n) end,
    roman = function(n) return pandoc.utils.to_roman_numeral(n):lower() end,
    Roman = function(n) return pandoc.utils.to_roman_numeral(n) end,
}

-- Split "label=(VS\arabic*)" into prefix "(VS", style "arabic", suffix ")"
local function parse_label(options)
    local label = options:match("label%s*=%s*{(.-)}%s*$") or options:match("label%s*=%s*([^,]+)")
    if not label then return nil end
    local prefix, style, suffix = label:match("^(.-)\\(%a+)%*(.*)$")
    if not prefix or not COUNTER_STYLES[style] then return nil end
    return {raw = label, prefix = prefix, style = style, suffix = suffix}
end

-- The item indent fits the widest label ("(a)" gets a narrow gutter, "(VS10)" a wider one)
local function labeled_list_div(items, labels)
    local widest = 0
    for _, text in ipairs(labels) do
        widest = math.max(widest, utf8.len(text) or #text)
    end
    return pandoc.Div({pandoc.BulletList(items)},
        pandoc.Attr("", {"labeled-list"}, {{"style", string.format("--label-chars: %d", widest)}}))
end

local function Div(div)
    if not div.classes:includes("enumerate") then return nil end
    local options = div.attributes["options"]
    if not options then return nil end
    local label = parse_label(options)
    if not label then
        io.stderr:write("Warning: unsupported enumerate options: " .. options .. "\n")
        return nil
    end

    -- Only the single-list case is supported; anything else is left for other filters
    if #div.content ~= 1 or div.content[1].t ~= "OrderedList" then
        io.stderr:write("Warning: .enumerate div must contain exactly one numbered list\n")
        return nil
    end
    local list = div.content[1]
    local start = list.listAttributes.start or 1

    if FORMAT:match("latex") then
        local blocks = {pandoc.RawBlock("latex", "\\begin{enumerate}[label=" .. label.raw .. "]")}
        if start ~= 1 then
            table.insert(blocks, pandoc.RawBlock("latex", string.format("\\setcounter{enumi}{%d}", start - 1)))
        end
        for _, item in ipairs(list.content) do
            table.insert(blocks, pandoc.RawBlock("latex", "\\item"))
            for _, block in ipairs(item) do
                table.insert(blocks, block)
            end
        end
        table.insert(blocks, pandoc.RawBlock("latex", "\\end{enumerate}"))
        return blocks
    end

    if FORMAT:match("html") then
        local items, labels = {}, {}
        for i, item in ipairs(list.content) do
            local text = label.prefix .. COUNTER_STYLES[label.style](start + i - 1) .. label.suffix
            table.insert(labels, text)
            local marker = pandoc.Span({pandoc.Str(text)}, pandoc.Attr("", {"item-label"}))
            local blocks = pandoc.Blocks(item)
            local first = blocks[1]
            if first and (first.t == "Plain" or first.t == "Para") then
                first.content:insert(1, pandoc.Space())
                first.content:insert(1, marker)
            else
                blocks:insert(1, pandoc.Plain({marker}))
            end
            table.insert(items, blocks)
        end
        return labeled_list_div(items, labels)
    end

    return nil
end

-- Plain Markdown lists with letters or roman numerals, e.g. solution parts written as
--
--     (a) First part.
--
--     A second paragraph of (a), not indented.
--
--     (b) Second part.
--
-- Pandoc ends the list at the unindented paragraph and starts a new list at (b). We merge
-- such runs back into one list (the paragraphs join the preceding item), then render the
-- list like a labeled .enumerate list, so both kinds look the same.

local FANCY_STYLES = {
    LowerAlpha = "alph", UpperAlpha = "Alph", LowerRoman = "roman", UpperRoman = "Roman",
}

local function list_label(attrs)
    local style = FANCY_STYLES[attrs.style]
    if not style then return nil end
    local delim = attrs.delimiter
    local prefix, suffix = "(", ")"
    if delim == "Period" then prefix, suffix = "", "."
    elseif delim == "OneParen" then prefix, suffix = "", ")" end
    return {raw = prefix .. "\\" .. style .. "*" .. suffix, prefix = prefix, style = style, suffix = suffix}
end

-- Blocks that may belong to a list item when they sit between two parts of one list
local function joinable(block)
    return block.t ~= "Header" and block.t ~= "HorizontalRule" and block.t ~= "OrderedList"
end

local function merge_split_lists(blocks)
    local result = pandoc.Blocks({})
    local i = 1
    while i <= #blocks do
        local block = blocks[i]
        if block.t == "OrderedList" then
            local attrs = block.listAttributes
            local next_number = (attrs.start or 1) + #block.content
            -- look ahead: joinable blocks, then a list of the same kind continuing the numbering
            local j = i + 1
            while j <= #blocks and joinable(blocks[j]) do j = j + 1 end
            local following = blocks[j]
            if j > i + 1 and following and following.t == "OrderedList"
                and following.listAttributes.style == attrs.style
                and following.listAttributes.delimiter == attrs.delimiter
                and (following.listAttributes.start or 1) == next_number
                and next_number > 1 then
                local last = block.content[#block.content]
                for k = i + 1, j - 1 do table.insert(last, blocks[k]) end
                for _, item in ipairs(following.content) do table.insert(block.content, item) end
                blocks[j] = block  -- continue merging from the combined list
                i = j
            else
                result:insert(block)
                i = i + 1
            end
        else
            result:insert(block)
            i = i + 1
        end
    end
    return result
end

local function render_list(list, label)
    local start = list.listAttributes.start or 1
    if FORMAT:match("latex") then
        local blocks = {pandoc.RawBlock("latex", "\\begin{enumerate}[label=" .. label.raw .. "]")}
        if start ~= 1 then
            table.insert(blocks, pandoc.RawBlock("latex", string.format("\\setcounter{enumi}{%d}", start - 1)))
        end
        for _, item in ipairs(list.content) do
            table.insert(blocks, pandoc.RawBlock("latex", "\\item"))
            for _, b in ipairs(item) do table.insert(blocks, b) end
        end
        table.insert(blocks, pandoc.RawBlock("latex", "\\end{enumerate}"))
        return blocks
    end
    if FORMAT:match("html") then
        local items, labels = {}, {}
        for i, item in ipairs(list.content) do
            local text = label.prefix .. COUNTER_STYLES[label.style](start + i - 1) .. label.suffix
            table.insert(labels, text)
            local marker = pandoc.Span({pandoc.Str(text)}, pandoc.Attr("", {"item-label"}))
            local blocks = pandoc.Blocks(item)
            local first = blocks[1]
            if first and (first.t == "Plain" or first.t == "Para") then
                first.content:insert(1, pandoc.Space())
                first.content:insert(1, marker)
            else
                blocks:insert(1, pandoc.Plain({marker}))
            end
            table.insert(items, blocks)
        end
        return labeled_list_div(items, labels)
    end
    return nil
end

local function OrderedList(list)
    local label = list_label(list.listAttributes)
    if not label then return nil end
    return render_list(list, label)
end

return {
    { Div = Div },
    { Blocks = merge_split_lists },
    { OrderedList = OrderedList },
}
