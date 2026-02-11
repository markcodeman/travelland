// Common utility functions extracted from existing components
// Provides shared patterns for error handling, loading states, and accessibility

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Hook for managing component loading and error states
 * @param {Function} asyncFunction - Async function to execute
 * @param {Array} dependencies - Dependencies array for useEffect
 * @returns {Object} { data, loading, error, retry }
 */
export function useAsyncState(asyncFunction, dependencies = []) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const execute = useCallback(async () => {
        setLoading(true);
        setError(null);
        
        try {
            const result = await asyncFunction();
            setData(result);
        } catch (err) {
            setError(err.message || 'An error occurred');
            console.error('Async operation failed:', err);
        } finally {
            setLoading(false);
        }
    }, [asyncFunction]);

    useEffect(() => {
        execute();
    }, dependencies);

    const retry = useCallback(() => {
        execute();
    }, [execute]);

    return { data, loading, error, retry };
}

/**
 * Hook for debouncing function calls
 * @param {Function} callback - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function useDebounce(callback, delay) {
    const timeoutRef = useRef(null);

    const debouncedCallback = useCallback((...args) => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }

        timeoutRef.current = setTimeout(() => {
            callback(...args);
        }, delay);
    }, [callback, delay]);

    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    return debouncedCallback;
}

/**
 * Hook for managing focus state
 * @returns {Object} { focused, onFocus, onBlur }
 */
export function useFocus() {
    const [focused, setFocused] = useState(false);

    const onFocus = useCallback(() => setFocused(true), []);
    const onBlur = useCallback(() => setFocused(false), []);

    return { focused, onFocus, onBlur };
}

/**
 * Hook for keyboard navigation
 * @param {Function} onEnter - Function to call on Enter key
 * @param {Function} onEscape - Function to call on Escape key
 * @returns {Function} Key handler function
 */
export function useKeyboardNavigation(onEnter, onEscape) {
    return useCallback((event) => {
        switch (event.key) {
            case 'Enter':
                if (onEnter) onEnter(event);
                break;
            case 'Escape':
                if (onEscape) onEscape(event);
                break;
            default:
                break;
        }
    }, [onEnter, onEscape]);
}

/**
 * Hook for managing modal/overlay state
 * @param {boolean} initialState - Initial open state
 * @returns {Object} { open, openModal, closeModal, toggleModal }
 */
export function useModal(initialState = false) {
    const [open, setOpen] = useState(initialState);

    const openModal = useCallback(() => setOpen(true), []);
    const closeModal = useCallback(() => setOpen(false), []);
    const toggleModal = useCallback(() => setOpen(prev => !prev), []);

    return { open, openModal, closeModal, toggleModal };
}

/**
 * Hook for managing local storage with state sync
 * @param {string} key - Storage key
 * @param {*} initialValue - Initial value
 * @returns {Array} [value, setValue]
 */
export function useLocalStorage(key, initialValue) {
    const [storedValue, setStoredValue] = useState(() => {
        try {
            const item = window.localStorage.getItem(key);
            return item ? JSON.parse(item) : initialValue;
        } catch (error) {
            console.error(`Error reading localStorage key "${key}":`, error);
            return initialValue;
        }
    });

    const setValue = useCallback((value) => {
        try {
            const valueToStore = value instanceof Function ? value(storedValue) : value;
            setStoredValue(valueToStore);
            window.localStorage.setItem(key, JSON.stringify(valueToStore));
        } catch (error) {
            console.error(`Error setting localStorage key "${key}":`, error);
        }
    }, [key, storedValue]);

    return [storedValue, setValue];
}

/**
 * Hook for detecting clicks outside an element
 * @param {Function} onClickOutside - Function to call when clicking outside
 * @returns {Object} ref object to attach to element
 */
export function useClickOutside(onClickOutside) {
    const ref = useRef(null);

    useEffect(() => {
        function handleClickOutside(event) {
            if (ref.current && !ref.current.contains(event.target)) {
                onClickOutside();
            }
        }

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [onClickOutside]);

    return ref;
}

/**
 * Hook for managing component visibility with intersection observer
 * @param {Object} options - Intersection observer options
 * @returns {Object} { ref, isVisible }
 */
export function useIntersectionObserver(options = {}) {
    const [isVisible, setIsVisible] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        const observer = new IntersectionObserver(([entry]) => {
            setIsVisible(entry.isIntersecting);
        }, options);

        const currentRef = ref.current;
        if (currentRef) {
            observer.observe(currentRef);
        }

        return () => {
            if (currentRef) {
                observer.unobserve(currentRef);
            }
        };
    }, [options]);

    return { ref, isVisible };
}

/**
 * Utility function to format error messages
 * @param {Error|string} error - Error object or message
 * @returns {string} Formatted error message
 */
export function formatError(error) {
    if (!error) return 'An unknown error occurred';
    
    if (typeof error === 'string') {
        return error;
    }
    
    if (error.message) {
        return error.message;
    }
    
    return 'An unexpected error occurred';
}

/**
 * Utility function to generate unique IDs
 * @param {string} prefix - ID prefix
 * @returns {string} Unique ID
 */
export function generateId(prefix = 'component') {
    return `${prefix}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Utility function to validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid email
 */
export function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Utility function to format location display name
 * @param {Object} location - Location object
 * @returns {string} Formatted location name
 */
export function formatLocationName(location) {
    if (!location) return '';
    
    const parts = [location.name];
    if (location.state) parts.push(location.state);
    if (location.country) parts.push(location.country);
    
    return parts.join(', ');
}

/**
 * Utility function to truncate text with ellipsis
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @param {string} ellipsis - Ellipsis string
 * @returns {string} Truncated text
 */
export function truncateText(text, maxLength = 100, ellipsis = '...') {
    if (!text || text.length <= maxLength) {
        return text;
    }
    
    return text.slice(0, maxLength - ellipsis.length) + ellipsis;
}

/**
 * Utility function to capitalize first letter
 * @param {string} string - String to capitalize
 * @returns {string} Capitalized string
 */
export function capitalizeFirst(string) {
    if (!string) return '';
    return string.charAt(0).toUpperCase() + string.slice(1).toLowerCase();
}

/**
 * Utility function to create accessible button props
 * @param {string} label - Button label
 * @param {Function} onClick - Click handler
 * @param {Object} props - Additional props
 * @returns {Object} Button props
 */
export function createButtonProps(label, onClick, props = {}) {
    return {
        'aria-label': label,
        onClick: (event) => {
            if (onClick) onClick(event);
        },
        ...props
    };
}

/**
 * Utility function to create accessible link props
 * @param {string} href - Link href
 * @param {string} label - Link label
 * @param {Object} props - Additional props
 * @returns {Object} Link props
 */
export function createLinkProps(href, label, props = {}) {
    return {
        href,
        'aria-label': label,
        target: '_blank',
        rel: 'noopener noreferrer',
        ...props
    };
}

/**
 * Utility function to check if component is mounted
 * @returns {Object} { isMounted, cleanup }
 */
export function useIsMounted() {
    const isMountedRef = useRef(true);

    useEffect(() => {
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    return {
        isMounted: () => isMountedRef.current,
        cleanup: () => { isMountedRef.current = false; }
    };
}

/**
 * Utility function to throttle function calls
 * @param {Function} func - Function to throttle
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Throttled function
 */
export function throttle(func, delay) {
    let lastCall = 0;
    return function (...args) {
        const now = Date.now();
        if (now - lastCall < delay) {
            return;
        }
        lastCall = now;
        return func.apply(this, args);
    };
}

/**
 * Utility function to debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, delay) {
    let timeoutId;
    return function (...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Utility function to deep clone an object
 * @param {Object} obj - Object to clone
 * @returns {Object} Cloned object
 */
export function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') {
        return obj;
    }
    
    if (obj instanceof Date) {
        return new Date(obj.getTime());
    }
    
    if (obj instanceof Array) {
        return obj.map(item => deepClone(item));
    }
    
    const cloned = {};
    for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
            cloned[key] = deepClone(obj[key]);
        }
    }
    
    return cloned;
}