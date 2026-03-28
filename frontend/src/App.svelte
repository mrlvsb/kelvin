<script>
import ClassList from './ClassList.svelte';
import Router from 'svelte-spa-router';
import { user } from './global.js';

const routes = {
  '/': ClassList
};
</script>

{#if $user}
  <Router {routes} />
{/if}
