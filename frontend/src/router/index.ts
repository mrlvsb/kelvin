import { createRouter, createWebHistory } from 'vue-router';
import ClassList from '../Teacher/ClassList.vue';

const routes = [
    {
        path: '/',
        name: 'Home',
        component: ClassList
    }
];

const router = createRouter({
    history: createWebHistory('/#/'),
    routes
});

export default router;
