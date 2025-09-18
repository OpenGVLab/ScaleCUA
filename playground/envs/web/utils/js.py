find_clickable_elements_js_code = """
    () => {
        try {
            function getElementText(element) {
                if (!element) return {};
    
                let textMap = {
                    textContent: element.textContent,
                    innerText: element.innerText,
                    value: element.value,
                    placeholder: element.placeholder,
                    alt: element.alt,
                    title: element.title,
                    ariaLabel: element.getAttribute("aria-label"),
                    dataTooltip: element.getAttribute("data-tooltip"),
                    dataTitleNoTooltip: element.getAttribute("data-title-no-tooltip"),
                    dataDescription: element.getAttribute("data-description"),
                    ariaDescription: element.getAttribute("aria-description"),
                    dataBsOriginalTitle: element.getAttribute("data-bs-original-title")
                };
    
                // Filter out null, undefined, and empty strings, and remove extra whitespaces
                let filteredTextMap = Object.fromEntries(
                    Object.entries(textMap)
                        .filter(([_, text]) => text && text.trim()) // Keep non-empty text
                        .map(([key, text]) => [key, text.trim().replace(/\s{2,}/g, " ")]) // Remove extra spaces
                );
    
                return filteredTextMap;
            }
    
    
            // Unified validation function
            function isValid(element) {
                const rect = element.getBoundingClientRect();
                // Check size and visibility
                const isVisible = rect.width > 5 && rect.height > 5 && 
                                          rect.top >= 0 && rect.left >= 0 &&
                                          rect.bottom <= window.innerHeight && rect.right <= window.innerWidth;
                if (!isVisible) {
                    return false;
                }
    
                // Check CSS visibility
                const style = window.getComputedStyle(element);
                if (style.display === "none" || style.visibility === "hidden" || element.hasAttribute("disabled")) {
                    return false;
                }
    
                // Check if element is on top
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                const topElement = document.elementFromPoint(centerX, centerY);
                let elementText = getElementText(element);
                let topElementText = getElementText(topElement);
                if (isFatherOrSameElement(topElement, element)) {
                   return true;
                }
                return false;
            };
    
            function getPointerElements() {
                let allElements = Array.from(document.querySelectorAll('*'));
    
                return allElements.filter(element => {
                    try {
                        let hasPointer = window.getComputedStyle(element).cursor === "pointer";
                        let canClickFlag = isValid(element);
                        return hasPointer && canClickFlag;
                    } catch (error) {
                        console.error("Error checking cursor:", error);
                        return false;
                    }
                });
            };
    
            function getClickableEvidenceElements() {
                let allElements = Array.from(document.querySelectorAll('*'));
    
                return allElements.filter(element => {
                    try {
                        let tagName = element.tagName.toLowerCase();
                        let roleAttr = element.getAttribute("role");
    
                        let hasClickableEvidence = (
                            ["a", "button", "select", "textarea", "option", "input"].includes(tagName) ||
                            element.hasAttribute("onclick") ||
                            (roleAttr && ["button", "option", "tab"].includes(roleAttr.toLowerCase()))
                        );
    
                        let canClickFlag = isValid(element);
    
                        return hasClickableEvidence && canClickFlag;
                    } catch (error) {
                        console.error("Error filtering element:", error);
                        return false;
                    }
                });
            }
    
            // Keep only top-level elements to avoid nested propagation
            function filterTopLevelElements(elements) {
                return elements.filter(element => 
                    !elements.some(other => other !== element && other.contains(element))
                );
            };
    
            // Determine whether A is the same as or a child of B
            function isFatherOrSameElement(element, fatherElement) {
                let simpleElementText = element.textContent || "";
                let simpleFatherElementText = fatherElement.textContent || ""; 
                if (
                    fatherElement === element || fatherElement.contains(element) 
                        || (simpleElementText !== "" && (simpleFatherElementText == simpleElementText || simpleFatherElementText.includes(simpleElementText)))
                ) {
                    return true;
                }
                return false;
            };
    
    
            function findClickableElements() {
                let clickableElements = getClickableEvidenceElements();
    
                // Get pointer-style elements and filter top-level ones
                let pointerElements = getPointerElements();
                pointerElements = filterTopLevelElements(pointerElements);
    
                // Remove duplicates and overlaps between pointer and known clickable elements
                pointerElements = pointerElements.filter(pointerElement => 
                    !clickableElements.some(
                        clickableElement => isFatherOrSameElement(pointerElement, clickableElement) 
                            || isFatherOrSameElement(clickableElement, pointerElement) 
                    )
                );
                clickableElements = [...clickableElements, ...pointerElements];
    
                let curIndex = 0;
                let clickableElementsInfo = [];
    
                clickableElements.forEach((element, index) => {
                    try {
                        const rect = element.getBoundingClientRect();
                        let elementText = getElementText(element);
                        let tagName = element.tagName.toLowerCase();
    
                        let elementInfo = {
                            id: curIndex,
                            type: element.getAttribute("type"),
                            bbox: [rect.left, rect.top, rect.right, rect.bottom],
                            tag: tagName
                        };
    
                        Object.assign(elementInfo, elementText);
                        clickableElementsInfo.push(elementInfo);
                        curIndex = curIndex + 1;
                    } catch (error) {
                        console.error("Error processing element:", error);
                    }
                });
    
                return clickableElementsInfo;
            }
    
            return findClickableElements();
        } catch (error) {
            console.error("Error in main JS execution:", error);
            return { error: error.toString(), filteredClickableElementsInfo: [], filteredClickableElements: [] };
        }
    }
"""
