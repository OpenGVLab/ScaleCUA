// Resources:
// https://html.spec.whatwg.org/multipage/interaction.html#the-tabindex-attribute
// https://allyjs.io/data-tables/focusable.html

(() => {

    function cleanHTML(htmlString) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlString, 'text/html');
    
        // Define the allowed attributes
        const allowedAttributes = [
            'aria', 'title', 'alt', 'label', 'aria-label', 'value', 'src', 
            'href', 'data-', 'placeholder', 'role', 'id', 'class'
        ];
    
        function truncate(value, maxLength = 50) {
            return value.length > maxLength ? value.substring(0, maxLength - 2) + '..' : value;
        }
    
        function getBasename(url) {
            const basename = url.split('/').pop();
            return basename.length > 25 ? basename.slice(-25) : basename;
        }
    
        function cleanElement(element) {
            const cleanedElement = document.createElement(element.tagName);
    
            Array.from(element.attributes).forEach(attr => {
                if (allowedAttributes.some(allowed => attr.name.startsWith(allowed))) {
                    let value = attr.value;
                    if (attr.name === 'src' || attr.name === 'href') {
                        value = getBasename(attr.value);
                    }
                    value = truncate(value);
                    cleanedElement.setAttribute(attr.name, value);
                }
            });
    
            Array.from(element.childNodes).forEach(child => {
                if (child.nodeType === Node.TEXT_NODE) {
                    cleanedElement.appendChild(document.createTextNode(child.textContent.trim()));
                } else if (child.nodeType === Node.ELEMENT_NODE) {
                    const cleanedChild = cleanElement(child);
                    cleanedElement.appendChild(cleanedChild);
                }
            });
    
            return cleanedElement;
        }
    
        const cleanedBody = cleanElement(doc.body);
    
        return cleanedBody.innerHTML;
    }
    

    
    const recursiveElementFromPoint = (x, y) => {
        let element = document.elementFromPoint(x, y);
        while (element && element.shadowRoot) {
            const shadowElement = element.shadowRoot.elementFromPoint(x, y);
            if (!shadowElement || shadowElement === element) {
                break;
            }
            element = shadowElement;
        }
        return element;
    };

    const querySelectorAll = (node,selector) => {
        const nodes = [...node.querySelectorAll(selector)],
            nodeIterator = document.createNodeIterator(node, Node.ELEMENT_NODE);
        let currentNode;
        while (currentNode = nodeIterator.nextNode()) {
            if(currentNode.shadowRoot) {
                nodes.push(...querySelectorAll(currentNode.shadowRoot,selector));
            }
        }
        return nodes;
    }

    const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    
    let _debug = [];
    
    // Step 0: Select all tabbables, videos, iframes, and svg icons in the page
    const tabbableQuery = `a[href]:not([tabindex='-1']),
            area[href]:not([tabindex='-1']),
            input:not([disabled]):not([tabindex='-1']),
            select:not([disabled]):not([tabindex='-1']),
            textarea:not([disabled]):not([tabindex='-1']),
            button:not([disabled]):not([tabindex='-1']),
            iframe:not([tabindex='-1']),
            [tabindex]:not([tabindex='-1']),
            [contentEditable=true]:not([tabindex='-1'])`;
    const otherQuery = `[role], [aria-label], [onclick]`;
    let items = [...querySelectorAll(document, `${tabbableQuery}, ${otherQuery}, video, iframe, svg`)].map(el => {
        return { 
            el
        };
    });

    // Acquire unobstructed bounding boxes
    items = items.map(item => {
        const rects = [...item.el.getClientRects()].filter(bb => {
            var center_x = bb.left + bb.width / 2;
            var center_y = bb.top + bb.height / 2;
            var elAtCenter = recursiveElementFromPoint(center_x, center_y);

            return elAtCenter === item.el || item.el.contains(elAtCenter);
        })

        return { rects, ...item };
    });

    // Filter out non-visible elements
    items = items.filter(item => {
        const area = item.rects.reduce((acc, rect) => acc + rect.width * rect.height, 0);
        return (area >= 1);
    });

    // Filter out elements that are contained within other elements from the list,
    // ensuring that only the topmost clickable items remain.
    items = items.filter(x => !items.some(y => x.el.contains(y.el) && !(x == y)));

    // Visualize labels
    // items.forEach(function(item, index) {
    //     item.rects.forEach((bbox) => {
    //     newElement = document.createElement("div");
    //     var borderColor = "red";
    //     newElement.style.outline = `2px solid ${borderColor}`;
    //     newElement.style.opacity = "0.8";
    //     newElement.style.position = "fixed";
    //     newElement.style.left = bbox.left + "px";
    //     newElement.style.top = bbox.top + "px";
    //     newElement.style.width = bbox.width + "px";
    //     newElement.style.height = bbox.height + "px";
    //     newElement.style.pointerEvents = "none";
    //     newElement.style.boxSizing = "border-box";
    //     newElement.style.zIndex = 2147483647;
    //     // newElement.style.background = `${borderColor}80`;
        
    //     // Add floating label at the corner
    //     var label = document.createElement("span");
    //     label.textContent = index;
    //     label.style.position = "absolute";
    //     label.style.top = "-19px";
    //     label.style.left = "0px";
    //     label.style.background = borderColor;
    //     label.style.color = "white";
    //     label.style.padding = "2px 4px";
    //     label.style.fontSize = "12px";
    //     label.style.borderRadius = "2px";
    //     newElement.appendChild(label);
        
    //     document.body.appendChild(newElement);
    //     // item.element.setAttribute("-ai-label", label.textContent);
    //     });
    // })

    
    const normal = (left, top, right, bottom) => {
        return [left / vw, top / vh, right / vw, bottom / vh]
    }

    return [ items.map(item => {
        // Find the first inner text node
        // This gives a natural target for larger interactive entities
        let firstTextNodeRect = null;
        const walker = document.createTreeWalker(item.el, NodeFilter.SHOW_TEXT, {
            acceptNode: node => node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP
        });
        const firstTextNode = walker.nextNode();
        textContent = item.el.textContent.trim()
        if (firstTextNode) {
            const range = document.createRange();
            range.selectNodeContents(firstTextNode);
            firstTextNodeRect = range.getBoundingClientRect();
            textContent = firstTextNode.textContent
        }
        hasText = textContent.length > 0
        if (!hasText) {
            try {
                textContent = cleanHTML(item.el.outerHTML)
            } catch (_) {
                textContent = item.el.outerHTML
            }
        }
        
        const bboxes = item.rects.map(({left, top, width, height}) => normal(left, top, left + width, top + height))
        return {
            x: (item.rects[0].left + item.rects[0].right) / 2, 
            y: (item.rects[0].top + item.rects[0].bottom) / 2,
            bboxs: bboxes,
            rect: firstTextNodeRect ? 
                normal(firstTextNodeRect.left, firstTextNodeRect.top, firstTextNodeRect.right, firstTextNodeRect.bottom) : bboxes[0],
            html: item.el.outerHTML,
            textContent,
            hasText: hasText,
            nodeType: item.el.tagName.toUpperCase()
        }
    }), [window.innerWidth, window.innerHeight], document.title ];
    
})()