<script>
import flatpickr from 'flatpickr';
export let from;
export let to;
export let timeOffsetInWeek;
export let semesterBeginDate;
export let onFromDuplicateClick;
export let onToDuplicateClick;
export let onToRelativeClick;

let fromEl, toEl;
let instanceFrom, instanceTo;

$: if (fromEl && toEl) {
  const opts = {
    enableTime: true,
    time_24hr: true,
    altFormat: 'd. m. Y H:i',
    altInput: true
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
  if (!from) {
    from = new Date();
  }

  let date = new Date(from);
  date.setMinutes(date.getMinutes() + minutes);
  to = date;
}

$: if (instanceFrom) {
  instanceTo.set('minDate', from);
  instanceFrom.setDate(from);
}
$: if (instanceTo) {
  instanceTo.setDate(to);
  if (!from) instanceTo._input.setAttribute('disabled', 'disabled');
  else if (instanceTo._input.hasAttribute('disabled'))
    instanceTo._input.removeAttribute('disabled');
}
</script>

<div class="input-group input-group-sm col-md">
  <button
    class="btn btn-primary dropdown-toggle"
    data-bs-toggle="dropdown"
    type="button"
    aria-expanded="false"></button>
  <ul class="dropdown-menu">
    <button class="dropdown-item" on:click={() => (from = new Date())}>Now</button>
    {#each { length: 14 } as _, i}
      <button class="dropdown-item" on:click={() => (from = weekDate(i))}>
        Week {i + 1}
        {#if weekStart(i) <= new Date() && new Date() <= weekStart(i + 1)}
          <span><span class="iconify" data-icon="akar-icons:arrow-back"></span></span>
        {/if}
      </button>
    {/each}
  </ul>
  <input bind:this={fromEl} class="form-control" bind:value={from} placeholder="Assigned" />
  <button
    class="btn btn-sm btn-secondary"
    title="Set assigned date to all visible classes"
    disabled={!from}
    on:click|preventDefault={() => onFromDuplicateClick(from)}>
    <span class="iconify" data-icon="mdi:content-duplicate"></span>
  </button>
</div>

<div class="input-group input-group-sm col-md">
  <button
    class="btn btn-primary dropdown-toggle"
    data-bs-toggle="dropdown"
    type="button"
    aria-expanded="false"
    disabled={!from}></button>
  <ul class="dropdown-menu">
    <button class="dropdown-item" on:click={() => addDeadline(30)}>+ 30 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(1 * 45)}>+ 1×45 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(2 * 45)}>+ 2×45 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(3 * 45)}>+ 3×45 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(1 * 60)}>+ 1×60 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(2 * 60)}>+ 2×60 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(3 * 60)}>+ 3×60 min</button>
    <button class="dropdown-item" on:click={() => addDeadline(60 * 24 * 7)}>+ week</button>
  </ul>
  <input bind:this={toEl} class="form-control" bind:value={to} placeholder="Deadline" />
  <button
    class="btn btn-sm btn-secondary"
    title="Set deadline to all assigned classes"
    disabled={!to}
    on:click|preventDefault={() => onToDuplicateClick(to)}>
    <span class="iconify" data-icon="mdi:content-duplicate"></span>
  </button>
  <button
    class="btn btn-sm btn-secondary"
    title="Set relative deadline to all assigned classes"
    disabled={!to}
    on:click|preventDefault={() => onToRelativeClick(from, to)}>
    <span class="iconify" data-icon="mdi:calendar-sync"></span>
  </button>
</div>
