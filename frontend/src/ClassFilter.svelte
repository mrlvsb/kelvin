<script>
    import {fetch} from './api.js'
    import {user} from './global.js'
    import {push} from 'svelte-spa-router'

    let semesters = {};
    let teachers = [];
    let allTeachers = [];
    let classes = [];
    let allClasses = [];

    export let semester;
    export let subject;
    export let teacher;
    export let clazz;

    async function load() {
      const res = await fetch('/api/classes/all');
      const json = await res.json();
      semesters = json['semesters'];

      let allTeachersSet = new Set();
      let allClassesSet = new Set();
      for (const semester in semesters) {
        for (const subject in semesters[semester]) {
          for (const teacher in semesters[semester][subject]) {
            allTeachersSet.add(teacher);
            for (const class_code of semesters[semester][subject][teacher]) {
              allClassesSet.add(class_code);
            }
          }
        }
      }
      allTeachers = [...allTeachersSet];
      allClasses = [...allClassesSet];
    }

    function resetClass() {
        clazz = undefined;
    }

    function fillTeacher() {
      if(subject && semesters[semester][subject].hasOwnProperty($user.username) >= 0) {
        teacher = $user.username;
      }
      resetClass();
    }

    $: if(semesters) {
      let subjs = [];
      const sem = semesters[semester];
      if(sem) {
        for(const subj in sem) {
          if(sem[subj].hasOwnProperty($user.username) >= 0) {
            subjs.push(subj);
          }
        }
      }
    }

    $: {
        if(semesters && semesters[semester]) {
          if(!semesters[semester][subject]) {
            subject = null;
          } else if(semesters[semester][subject].hasOwnProperty(teacher) < 0) {
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

    $: {
        if (semester && subject && semesters[semester]?.[subject]) {
          teachers = Object.keys(semesters[semester][subject]);
          if (teacher && semesters[semester]?.[subject]?.[teacher]) {
            classes = semesters[semester][subject][teacher];
          } else {
            let filteredClasses = [];
            for (const t in semesters[semester][subject]) {
                filteredClasses.push(...semesters[semester][subject][t]);
            }
            classes = filteredClasses;
          }
        } else {
          teachers = allTeachers;
          classes = allClasses;
        }
    }

    function sorted(items, compare_fn) {
      items.sort(compare_fn);
      return items;
    }

    function compare_semester(a, b) {
      let year_a = Number(a.substring(0, 4));
      let year_b = Number(b.substring(0, 4));
      if (year_a < year_b) {
        return -1;
      } else if (year_a > year_b) {
        return 1;
      } else {
        return a[4] === "W" ? -1 : 1;
      }
    }

    load();
</script>

<div class="ms-auto">
  <div class="input-group">
    <select class="form-select form-select-sm" bind:value={semester} on:change={resetClass}>
        <option value="" disabled>Semester</option>
        {#each sorted(Object.keys(semesters), compare_semester) as semester (semester)}
            <option>{semester}</option>
        {/each}
    </select>

    <select class="form-select form-select-sm" bind:value={subject} on:change={fillTeacher} disabled={!semester}>
        <option value="">Subject</option>
        {#if semesters && semesters[semester]}
            {#each sorted(Object.keys(semesters[semester])) as subj (subj)}
                <option>{subj}</option>
            {/each}
        {/if}
    </select>

    {#if $user.is_superuser}
      <select class="form-select form-select-sm" bind:value={teacher} on:change={resetClass}>
          <option value="">Teacher</option>
            {#each sorted(teachers) as teacher (teacher)}
                <option>{teacher}</option>
            {/each}
      </select>
    {/if}
    <select class="form-select form-select-sm" bind:value={clazz} disabled={!(semester && subject)}>
      <option value="">Class</option>
      <!-- `classes` are sorted serverside -->
      {#each classes as clazz (clazz)}
        <option>{clazz}</option>
      {/each}
    </select>
  </div>
</div>
