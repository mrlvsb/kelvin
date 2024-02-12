<script setup lang="ts">
  //import HelloWorld from './components/HelloWorld.vue'
  //import ClassDetail from "./ClassDetail.vue"

  import { onMounted } from 'vue'
  import { ref } from 'vue'

  import { csrfToken} from "./api.ts";
  import MyClassDetail from "./MyClassDetail.vue";
  //import {semester, user} from './global.ts'


  //let classes = null;
  let loading = true;

  let classes = ref(Array<Class>());


  let filter = {
        semester: "2023W",//semester.abbr,
        subject: null,
        teacher: "GAU01",//user.username,
        class: null,
  };

  interface Assignment {
      task_id: number
      task_link: string // URL
      assignment_id: number
      name: string
      short_name: string
      moss_link: string // URL
      sources_link: string // URL
      csv_link: string // URL
      assigned: string // datetime
      deadline: string // datetime
      max_points: number
  }

  interface Student {
      student: string // login
      submits: number
      submits_with_assigned_pts: number
      first_submit_date: string // datetime
      last_submit_date: string // datetime
      points: null
      max_points: null
      assigned_points: number
      accepted_submit_num: number
      accepted_submit_id: number
      color: string
      link: string // URL
  }

  interface Class {
      id: number
      teacher_username:	string
      timeslot:	string
      code:	string
      subject_abbr:	string
      csv_link: string // URL
      assignments: Assignment[]
      summary: string
      students: Student[]
  }

  let prevParams;
  async function refetch(): Promise<Class[]> {
      // We can use the `Headers` constructor to create headers
      // and assign it as the type of the `headers` variable
      const headers: Headers = new Headers()
      // Add a few headers
      headers.set('Content-Type', 'application/json')
      headers.set('Accept', 'application/json')
      // Add a custom header, which we can use to check
      //headers.set('X-Custom-Header', 'CustomValue')
      headers.set('Access-Control-Allow-Origin', '*')
      //headers.set('X-CSRFToken', csrfToken())

      // Create the request object, which will be a RequestInfo type.
      // Here, we will pass in the URL as well as the options object as parameters.
      const request: RequestInfo = new Request(`/api/classes?semester=${filter.semester}&teacher=${filter.teacher}`, {
          method: 'GET',
          headers: headers
      })

      const params = new URLSearchParams(Object.fromEntries(Object.entries(filter).filter(([_, v]) => v))).toString();
      if(prevParams === params) {
          return;
      }
      prevParams = params;
      loading = true;

      const req = await fetch(request);

      //const req = await fetch('/api/classes?' + params);
      const res = await req.json();
      classes.value = res['classes'].map(c => {
        c.assignments = c.assignments.map(assignment => {
          assignment.assigned = new Date(assignment.assigned);
          if(assignment.deadline) {
            assignment.deadline = new Date(assignment.deadline);
          }
          return assignment;
        });
        return c;
      });
      loading = false;

      console.log(classes);
    }

    // For our example, the data is stored on a static `users.json` file
    //return fetch(request)
      // the JSON body is taken from the response
      //.then(res => res.json())
      //.then(res => {
        // The response has an `any` type, so we need to cast
        // it to the `User` type, and return it from the promise
        //return res as Class[]
      //})
  //}

  //const result = document.getElementById('result')
  //if (!result) {
  //  throw new Error('No element with ID `result`')
  //}
  //var apidata = {}

  //getUsers()
  //  .then(users => {
  //    //result.innerHTML = users.map(u => u.name).toString()
  //      apidata = users
  //  })

  onMounted(() => {
      refetch()
  })
  /*


  import ClassDetail from './ClassDetail.svelte'
  import {querystring, link} from 'svelte-spa-router'
  import SyncLoader from './SyncLoader.svelte'
  import ClassFilter from './ClassFilter.svelte'
  import {semester, user} from './global.js'

  //let classes = null;
  //let loading = true;

  let filter = {
        semester: $semester.abbr,
        subject: null,
        teacher: $user.username,
        class: null,
  };

  //onMount(async () => {
  //  await refetch();
  //});

  let prevParams;
  async function refetch() {
    const params = new URLSearchParams(Object.fromEntries(Object.entries(filter).filter(([_, v]) => v))).toString();
    if(prevParams === params) {
        return;
    }
    prevParams = params;
    loading = true;

    const req = await fetch('/api/classes?' + params);
    const res = await req.json();
    classes = res['classes'].map(c => {
      c.assignments = c.assignments.map(assignment => {
        assignment.assigned = new Date(assignment.assigned);
        if(assignment.deadline) {
          assignment.deadline = new Date(assignment.deadline);
        }
        return assignment;
      });
      return c;
    });
    loading = false;
  }

  $: {
      if($querystring.length) {
        filter = Object.fromEntries(new URLSearchParams($querystring));
      }
      refetch();
  }
  */
</script>

<template>
  <div class="container-fluid p-1">
    <div class="d-flex mb-1">

    </div>
    <div class="classes">
      <div class="classes-inner">
        <MyClassDetail v-for="clazz in classes" :clazz="clazz" />
      </div>
    </div>
  </div>
</template>


<style scoped>
</style>

