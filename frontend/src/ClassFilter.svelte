<script>
    import {fetch} from './api.js'
    import {user} from './global.js'
    import {link, push} from 'svelte-spa-router'

    let semesters = {};
    let allTeachers = [];


    export let semester;
    export let subject;
    export let teacher;
    export let clazz;

    async function load() {
      const res = await fetch('/api/classes/all');
      const json = await res.json();
      semesters = json['semesters'];

      allTeachers = new Set();
      for(let s in semesters) {
        for(let subj in semesters[s]) {
          allTeachers = [...new Set([...allTeachers, ...semesters[s][subj]])];
        }
      }
    }

    function fillTeacher() {
      if(subject && semesters[semester][subject].indexOf($user.username) >= 0) {
        teacher = $user.username;
      }
    }

    $: if(semesters) {
      let subjs = [];
      const sem = semesters[semester];
      if(sem) {
        for(const subj in sem) {
          if(sem[subj].indexOf($user.username) >= 0) {
            subjs.push(subj);
          }
        }
      }
    } 

    $: {
        if(semesters && semesters[semester]) {
          if(!semesters[semester][subject]) {
            subject = null;
          } else if(semesters[semester][subject].indexOf(teacher) < 0) {
            teacher = null;
          }
        }

        const params = new URLSearchParams(Object.fromEntries(Object.entries({
            'semester': semester,
            'subject': subject,
            'teacher': teacher,
            'class': clazz,
        }).filter(([_, v]) => v)));
        push('/?' + params);
    }

    $: teachers = semester && subject && semesters && semesters[semester] && semesters[semester][subject] ? semesters[semester][subject] : allTeachers;

    load();
</script>

<div class="ml-auto">
  <div class="input-group">
    <select class="custom-select custom-select-sm" bind:value={semester}>
        <option value="">Semester</option>
        {#each Object.keys(semesters)as semester (semester)}
            <option>{semester}</option>
        {/each}
    </select>

    <select class="custom-select custom-select-sm" bind:value={subject} on:change={fillTeacher} disabled={!semester}>
        <option value="">Subject</option>
        {#if semesters && semesters[semester]}
            {#each Object.keys(semesters[semester]) as subj (subj)}
                <option>{subj}</option>
            {/each}
        {/if}
    </select>

    {#if $user.is_superuser}
      <select class="custom-select custom-select-sm" bind:value={teacher}>
          <option value="">Teacher</option>
            {#each teachers as teacher (teacher)}
                <option>{teacher}</option>
            {/each}
      </select>
    {/if}
  </div>
</div>
