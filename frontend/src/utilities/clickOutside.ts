import { Directive } from 'vue';

/**
 * Custom directive used in vue components to detect clicks outside HTML tag.
 * Is it necessary to use lambda as function as evaluation is not lazy.
 *
 * @example
 *  <script>
 *  import { clickOutside } from 'clickOutside';
 *  const vClickOutside = clickOutside;
 *  </script>
 *
 *  <template>
 *  <tag v-click-outside="() => { 'your code here' } />
 *  </template>
 *
 */
export const clickOutside: Directive = {
    mounted(node: HTMLElement, binding) {
        const handler = (event: MouseEvent) => {
            if (node && !node.contains(event.target as Node)) {
                binding.value(event);
            }
        };

        //save handler to remove it on unmounted
        (node as any)._clickOutsideHandler = handler;

        document.addEventListener('click', handler, true);
    },

    unmounted(node: HTMLElement) {
        document.removeEventListener('click', (node as any)._clickOutsideHandler, true);
    }
};
