import {writable} from 'svelte/store'

export function clickOutside(node) {
  const handleClick = event => {
    if (node && !node.contains(event.target) && !event.defaultPrevented) {
      node.dispatchEvent(
        new CustomEvent('click_outside', node)
      )
    }
  }

  document.addEventListener('click', handleClick, true);

  return {
    destroy() {
      document.removeEventListener('click', handleClick, true);
    }
  }
}

let localStorageStores = {};
export function localStorageStore(key, initialValue) {
  if(!(key in localStorageStores)) {
      const saved = localStorage.getItem(key);
      if(saved) {
        try {
          initialValue = JSON.parse(saved);
        } catch(exception) {
          console.log(`Failed to load ${key}: ${exception}`);
        }
      }

      const {subscribe, set} = writable(initialValue);

      localStorageStores[key] = {
        subscribe,
        set(value) {
          localStorage.setItem(key, JSON.stringify(value));
          set(value);
        },
      }
  }
  return localStorageStores[key];
}
