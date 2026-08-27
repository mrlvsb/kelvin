<script>
import ClassList from './ClassList.svelte';
import Router from 'svelte-spa-router';
import { user, semester } from './global.js';

const routes = {
  '/': ClassList
};

// The Svelte home page owns the /api/info fetch for its own store consumers
// (ClassList/ClassDetail/ClassFilter). Vue pages fetch it themselves.
fetch('/api/info')
  .then((res) => res.json())
  .then((data) => {
    data['semester']['begin'] = new Date(data['semester']['begin']);
    data['semester']['begin'].setHours(0);

    semester.set(data['semester']);
    user.set(data['user']);
  });
</script>

{#if $user}
  <Router {routes} />
{/if}
