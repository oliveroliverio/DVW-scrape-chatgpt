// chatgpt_to_md.js
// Returns the current conversation as Markdown when you call getChatMarkdown().
// For browser testing in Sources > Snippets, you can run:
//   const markdown = getChatMarkdown();
//   // console.log(markdown);

// Prefer the real code area and always read raw DOM text (visibility-independent)
function extractCodeText(preOrCodeEl) {
    // If a <pre>, try the scrollable code area first, then any <code>, else the <pre> itself
    const codeNode =
        (preOrCodeEl.tagName?.toLowerCase() === 'pre'
            ? (preOrCodeEl.querySelector('div.overflow-y-auto code') ||
                preOrCodeEl.querySelector('code'))
            : preOrCodeEl);

    // IMPORTANT: use textContent, not innerText (innerText can be empty in overflowed blocks)
    return (codeNode?.textContent || preOrCodeEl.textContent || '').trim();
}

function normalizeYouTubeUrl(raw) {
    if (!raw) return '';
    try {
        const u = new URL(raw, location.href);

        if (u.hostname.includes('youtu.be')) {
            const id = u.pathname.split('/').filter(Boolean)[0] || '';
            return id ? `https://www.youtube.com/watch?v=${id}` : raw;
        }
        if (u.hostname.includes('youtube.com') || u.hostname.includes('youtube-nocookie.com')) {
            if (u.pathname.startsWith('/embed/')) {
                const id = u.pathname.replace('/embed/', '').split('/')[0].split('?')[0];
                return id ? `https://www.youtube.com/watch?v=${id}` : raw;
            }
            if (u.pathname.startsWith('/embed/videoseries') && u.searchParams.get('list')) {
                return `https://www.youtube.com/playlist?list=${u.searchParams.get('list')}`;
            }
            if (u.pathname === '/watch' && u.searchParams.get('v')) {
                return `https://www.youtube.com/watch?v=${u.searchParams.get('v')}`;
            }
        }
        return raw;
    } catch { return raw; }
}

function labelForAnchor(node, href) {
    const text = processChildNodes(node).trim();
    if (text) return text;
    const altImg = node.querySelector('img[alt]')?.getAttribute('alt');
    const title = node.getAttribute('title') || node.getAttribute('aria-label');
    if (altImg) return altImg.trim();
    if (title) return title.trim();

    if (/youtu\.be|youtube\.com/.test(href)) {
        const watch = normalizeYouTubeUrl(href);
        try {
            const u = new URL(watch);
            return u.searchParams.get('v') || u.pathname.split('/').pop() || 'YouTube';
        } catch {
            return 'YouTube';
        }
    }
    try { return new URL(href).hostname; } catch { return href; }
}

function tableToMarkdown(tableEl) {
    if (!tableEl || tableEl.tagName.toLowerCase() !== 'table') return '';
    let markdown = '\n';
    const rows = tableEl.querySelectorAll('tr');
    if (!rows || rows.length === 0) return '';

    const headerRow = rows[0];
    const headerCells = headerRow.querySelectorAll('th');
    const useFirstRowAsHeader = headerCells.length === 0;
    const actualHeaderCells = useFirstRowAsHeader ? headerRow.querySelectorAll('td') : headerCells;
    if (actualHeaderCells.length === 0) return '';

    markdown += '| ';
    Array.from(actualHeaderCells).forEach(cell => {
        markdown += processChildNodes(cell).trim().replace(/\|/g, '\\|') + ' | ';
    });
    markdown = markdown.trim() + '\n';

    markdown += '| ';
    Array.from(actualHeaderCells).forEach(() => { markdown += '--- | '; });
    markdown = markdown.trim() + '\n';

    const startIndex = useFirstRowAsHeader ? 1 : 0;
    for (let i = startIndex;i < rows.length;i++) {
        const row = rows[i];
        const cells = row.querySelectorAll('td');
        if (cells.length === 0) continue;
        markdown += '| ';
        Array.from(cells).forEach(cell => {
            markdown += processChildNodes(cell).trim().replace(/\|/g, '\\|') + ' | ';
        });
        markdown = markdown.trim() + '\n';
    }
    return '\n' + markdown + '\n';
}

function nodeToMarkdown(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent || '';
    if (node.nodeType === Node.ELEMENT_NODE) {
        const tagName = node.tagName.toLowerCase();
        if (tagName === 'table') return tableToMarkdown(node);

        switch (tagName) {
            case 'h1': return `\n# ${processChildNodes(node).trim()}\n`;
            case 'h2': return `\n## ${processChildNodes(node).trim()}\n`;
            case 'h3': return `\n### ${processChildNodes(node).trim()}\n`;
            case 'h4': return `\n#### ${processChildNodes(node).trim()}\n`;
            case 'ul': return '\n' + processList(node, '* ') + '\n';
            case 'ol': return '\n' + processList(node, (i) => `${i + 1}. `) + '\n';
            case 'li': return processChildNodes(node);
            case 'pre': {
                // Read full code even if off-screen/overflowed
                const codeText = extractCodeText(node);

                // Detect language from classes like "language-bash"
                const codeEl = node.querySelector('div.overflow-y-auto code') || node.querySelector('code');
                let lang = '';
                if (codeEl) {
                    const cls = codeEl.getAttribute('class') || '';
                    const m = cls.match(/language-([\w-]+)/i);
                    if (m) lang = m[1];
                }

                return `\n\`\`\`${lang}\n${codeText}\n\`\`\`\n`;
            }
            case 'code': {
                // If this <code> sits inside <pre>, the <pre> branch already handled it.
                if (node.parentElement && node.parentElement.tagName.toLowerCase() === 'pre') {
                    return extractCodeText(node); // raw text
                }
                return `\`${extractCodeText(node)}\``; // inline code
            }
            case 'b':
            case 'strong': return `**${processChildNodes(node).trim()}**`;
            case 'i':
            case 'em': return `*${processChildNodes(node).trim()}*`;
            case 'span': return processChildNodes(node);

            case 'thead':
            case 'tbody':
            case 'tr':
            case 'th':
            case 'td': return processChildNodes(node);

            case 'a': {
                let href = node.getAttribute('href') || '';
                if (!href) return processChildNodes(node);
                try { href = new URL(href, location.href).toString(); } catch { }
                if (/youtu\.be|youtube\.com/.test(href)) href = normalizeYouTubeUrl(href);
                const label = labelForAnchor(node, href);
                return `[${label}](${href})`;
            }

            case 'iframe': {
                const src = node.getAttribute('src') || '';
                if (!src) return '';
                let url = src;
                try { url = new URL(src, location.href).toString(); } catch { }
                if (/youtu\.be|youtube\-nocookie\.com|youtube\.com/.test(url)) {
                    const watch = normalizeYouTubeUrl(url);
                    const label = node.getAttribute('title') || node.getAttribute('aria-label') || 'YouTube video';
                    return `\n[▶️ ${label}](${watch})\n`;
                }
                const label = node.getAttribute('title') || node.getAttribute('aria-label') || 'Embedded content';
                return `\n[🔗 ${label}](${url})\n`;
            }

            default: return processChildNodes(node);
        }
    }
    return '';
}

function processChildNodes(parent) {
    let result = '';
    parent.childNodes.forEach(child => { result += nodeToMarkdown(child); });
    return result;
}

function processList(listNode, bullet) {
    let result = '';
    const items = listNode.querySelectorAll(':scope > li');
    items.forEach((li, i) => {
        const prefix = (typeof bullet === 'function') ? bullet(i) : bullet;
        const content = processChildNodes(li).trim();
        // result += prefix + content.replace(/\n+/g, ' ') + '\n';
        // Render the item's markdown
        let itemMd = processChildNodes(li).trim();

        // If the list item contains block content (code, tables, headings, etc.),
        // DO NOT collapse newlines — preserve formatting.
        const hasBlock = li.querySelector('pre, table, blockquote, div, section, article, h1, h2, h3, h4');
        const containsFence = itemMd.includes('```');

        if (hasBlock || containsFence) {
            // Keep as-is so fenced code blocks render correctly.
            // Most markdown renderers accept block content immediately after the bullet.
            result += `${prefix}${itemMd}\n`;
        } else {
            // Simple text list item: OK to collapse internal newlines to spaces.
            result += `${prefix}${itemMd.replace(/\n+/g, ' ')}\n`;
        }
    });
    return result;
}

// --- MAIN: build Markdown from DOM ---
function getChatMarkdown() {
    // Title if present
    const titleNode = document.querySelector('h1, header h1, [data-testid="conversation-title"]');
    const title = titleNode ? titleNode.textContent.trim() : 'ChatGPT Conversation';
    let md = `# ${title}\n\n`;

    // Prefer explicit author roles if available
    const nodes = document.querySelectorAll('[data-message-author-role]');
    if (nodes.length) {
        nodes.forEach(n => {
            const role = (n.getAttribute('data-message-author-role') || '').toLowerCase();
            const who = role === 'user' ? '**User:**' : '**ChatGPT:**';
            const content = processChildNodes(n).trim();
            if (content) {
                md += `${who}\n\n${content}\n\n---\n\n`;
            }
        });
        return md;
    }

    // Fallback: older/newer layouts — try any message-ish blocks
    const guesses = document.querySelectorAll('[data-message-id], [data-testid="message"], article, section');
    guesses.forEach(el => {
        const text = el.innerText?.trim() || '';
        if (!text) return;
        // Heuristic author guess
        const who = el.querySelector('[data-message-author-role="user"]') ? '**User:**' :
            el.querySelector('[data-message-author-role]') ? '**ChatGPT:**' :
                '**Message:**';
        md += `${who}\n\n${processChildNodes(el).trim()}\n\n---\n\n`;
    });
    return md;
}

// For snippet testing in DevTools, uncomment:
// const markdown = getChatMarkdown();
// console.log(markdown);
