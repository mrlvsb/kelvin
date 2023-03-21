<script>
	import flatpickr from "flatpickr";
	import Dropdown from './Dropdown.svelte'
  import 'flatpickr/dist/flatpickr.min.css'
  export let from;
  export let to;
	export let timeOffsetInWeek;
	export let semesterBeginDate;

  let fromEl, toEl;
  let instanceFrom, instanceTo

  $: if(fromEl && toEl) {
    const opts = {
			enableTime: true,
      time_24hr: true,
      altFormat: "d. m. Y H:i",
      altInput: true,
    };

		instanceFrom = flatpickr(fromEl, opts);
		instanceTo = flatpickr(toEl, opts);
  }

  function weekDate(n) {
    let date = new Date(semesterBeginDate.getTime());
    date.setDate(date.getDate() + 7 * n);
    date.setSeconds(timeOffsetInWeek);
    return date;
  }

  function weekStart(n) {
    let date = new Date(semesterBeginDate.getTime());
    date.setDate(date.getDate() + 7 * n);
    return date;
  }

  function addDeadline(minutes) {
    if(!from) {
      from = new Date();
    }

    let date = new Date(from);
    date.setMinutes(date.getMinutes() + minutes);
    to = date;
  }

$: if(instanceFrom) {
  instanceTo.set('minDate', from);
  instanceFrom.setDate(from);
}
$: if(instanceTo) {
  instanceTo.setDate(to);
}


</script>
<style>
  input {
    background-color: #fff !important;
  }
  .dropdown-item {
    cursor: pointer;
  }
</style>

<div class="row">
  <div class="input-group input-group-sm col">
    <Dropdown>
      <span class="dropdown-item" on:click={() => from = new Date()}>Now</span>
      {#each {length: 14} as _, i}
        <span class="dropdown-item" on:click={() => from = weekDate(i)}>
          Week {i + 1}
          {#if weekStart(i) <= new Date() && new Date() <= weekStart(i + 1) }
            <span><span class="iconify" data-icon="akar-icons:arrow-back"></span></span>
          {/if}
        </span>
      {/each}
    </Dropdown>
    <input bind:this={fromEl} class="form-control" bind:value={from} placeholder="Assigned">
  </div>

  <div class="input-group input-group-sm col">
    <Dropdown>
      <span class="dropdown-item" on:click={() => addDeadline(30)}>+ 30 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(1*45)}>+ 1×45 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(2*45)}>+ 2×45 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(3*45)}>+ 3×45 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(1*60)}>+ 1×60 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(2*60)}>+ 2×60 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(3*60)}>+ 3×60 min</span>
      <span class="dropdown-item" on:click={() => addDeadline(60*24*7)}>+ week</span>
    </Dropdown>
    <input bind:this={toEl} class="form-control" bind:value={to} placeholder="Deadline">
  </div>
</div>
