import { describe, expect, it } from 'vitest';
import ThemeSelector from './ThemeSelector.vue';
import { mount } from '@vue/test-utils';
import { ThemeValue } from '../utilities/theme';

describe('ThemeSelector', () => {
    it('Auto option with no prop', () => {
        const wrapper = mount(ThemeSelector);
        expect(wrapper.html()).toMatchSnapshot();
    });
    it('Theme prop to auto', () => {
        const wrapper = mount(ThemeSelector, {
            props: {
                theme: 'auto' satisfies ThemeValue
            }
        });
        expect(wrapper.html()).toMatchSnapshot();
    });
    it('Theme prop to light', () => {
        const wrapper = mount(ThemeSelector, {
            props: {
                theme: 'light' satisfies ThemeValue
            }
        });
        expect(wrapper.html()).toMatchSnapshot();
    });
    it('Theme prop to dark', () => {
        const wrapper = mount(ThemeSelector, {
            props: {
                theme: 'dark' satisfies ThemeValue
            }
        });
        expect(wrapper.html()).toMatchSnapshot();
    });
});
