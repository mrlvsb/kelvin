<script>
	import flatpickr from "flatpickr";
  import rangePlugin from 'flatpickr/dist/plugins/rangePlugin'
	import Dropdown from './Dropdown.svelte'
  import 'flatpickr/dist/flatpickr.min.css'
  export let from;
  export let to;
	export let timeOffsetInWeek;
	export let semesterBeginDate;

  let fromEl, toEl;
  let instanceFrom, instanceTo
	let dropDownShown;

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

  function setWeek(n) {
    let date = new Date(semesterBeginDate.getTime());
    date.setDate(date.getDate() + 7 * n);
    date.setSeconds(timeOffsetInWeek);
    from = date;
  }

  function addDeadline(minutes) {
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
  <div class="input-group input-group-sm col-sm-6">
    <div class="input-group-prepend">
      <Dropdown>
        <span class="dropdown-item" on:click={() => from = new Date()}>Now</span>
        {#each {length: 14} as _, i}
          <span class="dropdown-item" on:click={() => setWeek(i)}>Week {i + 1}</span>
        {/each}
      </Dropdown>
    </div>
    <input bind:this={fromEl} class="fom-control" bind:value={from}>
  </div>

  <div class="input-group input-group-sm col-sm-6">
    <div class="input-group-prepend">
      <Dropdown>
        <span class="dropdown-item" on:click={() => addDeadline(30)}>+30 min</span>
        <span class="dropdown-item" on:click={() => addDeadline(60)}>+60 min</span>
        <span class="dropdown-item" on:click={() => addDeadline(180)}>+3 h</span>
        <span class="dropdown-item" on:click={() => addDeadline(60*24*7)}>week</span>
      </Dropdown>
    </div>
    <input bind:this={toEl} class="form-control" bind:value={to}>
  </div>
</div>
