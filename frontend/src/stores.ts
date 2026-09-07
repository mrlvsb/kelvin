import { ref } from 'vue';

export const HideCommentsState = {
    NONE: 'none',
    AUTOMATED: 'automated',
    ALL: 'all'
};

export const hideComments = ref(HideCommentsState.NONE);

export const ViewModeState = {
    LIST: 'list',
    TREE: 'tree'
};

export const viewMode = ref(ViewModeState.LIST);
