<script>
    import {fetch} from './api.js'

    let subject_inbus_selected = null;
    let subject_kelvin_selected = null;

    let semester = null;
    let busy = false;

    let semesters_data = null;
    let semesters = null;
    let subjects_inbus = null;
    let subjects_inbus_filtered = null;
    let subjects_kelvin = null;
    let subject_inbus_schedule = null;

    let classes_to_import = [];
    let result = null;

    $: canImport = classes_to_import.length && !busy;


    function svcc2num(svcc) {
        let [dept_code, version] = svcc.split('/');
        let [dept, code] = dept_code.split('-');

        let svcc_str = dept + code + version;
        let svcc_num = Number(svcc_str);
        
        return svcc_num;
    }


    async function loadInbusAndKelvinSubjects() {
        const res1 = await fetch('/api/inbus/subject_versions');
        const res2 = await fetch('/api/subjects/all');

        subjects_inbus = await res1.json();
        subjects_kelvin = await res2.json();

        subjects_kelvin = subjects_kelvin.subjects;
        subjects_kelvin.sort((a, b) => {
            const name_a = a.name.toUpperCase();
            const name_b = b.name.toUpperCase();
            if (name_a < name_b) {
                return -1;
            }
            if (name_a > name_b) {
                return 1;
            }
            return 0;
        });

        const subject_kelvin_abbrs = subjects_kelvin.map(s => s.abbr);

        subjects_inbus_filtered = subjects_inbus.filter(subject_inbus => subject_kelvin_abbrs.includes(subject_inbus.subject.abbrev));
        subjects_inbus_filtered = subjects_inbus_filtered.sort((a, b) => 
            svcc2num(a.subjectVersionCompleteCode) - svcc2num(b.subjectVersionCompleteCode));
    }


    function parseSemesters() {
        semesters = semesters_data.map(sm => ({'pk': sm.pk, 'year': sm.fields.year, 'winter': sm.fields.winter, 'display': new String(sm.fields.year) + (sm.fields.winter ? 'W' : 'S')}));
    }


    async function loadSemesters() {
        const res = await fetch('/api/semesters')
        semesters_data = await res.json();
        parseSemesters();
    }


    async function loadScheduleForSubjectVersionId() {
        let res = await fetch(`/api/inbus/schedule/subject/version/${subject_inbus_selected.subjectVersionId}`);
        subject_inbus_schedule = await res.json();
    }


    $: if (subject_inbus_selected) {
        loadScheduleForSubjectVersionId();
    }


    async function import_activities() {
        busy = true;
        const req = {
            'semester_id': semester,
            'subject': subject_kelvin_selected,
            'activities': classes_to_import,
        };

        const res = await fetch('/api/import/activities', {
            method: 'POST',
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(req),
        });

        result = (await res.json());
        busy = false;
    }

    loadSemesters();
    loadInbusAndKelvinSubjects();
</script>


{#if semesters}
<select bind:value={semester}>
    {#each semesters as item}
    <option value="{item.pk}">{item.display}</option>
    {/each}
</select>
{/if}


{#if subjects_kelvin}
<select bind:value={subject_kelvin_selected}>
    {#each subjects_kelvin as item}
    <option value={item}>{item.abbr} - {item.name}</option>
    {/each}
</select>
{/if}


{#if subjects_inbus_filtered}
<select bind:value={subject_inbus_selected}>
    {#each subjects_inbus_filtered as item}
    <option value={item}>{item.subjectVersionCompleteCode} - {item.subject.abbrev} - {item.subject.title}</option>
    {/each}
</select>
{/if}


{#if subject_inbus_schedule}
<table class="table table-hover table-stripped table-sm">
    <tbody>
    {#each subject_inbus_schedule as ca} <!-- `ca` stands for concrete_activity -->
    <tr>
        <td>
            <label>
                <input type="checkbox" bind:group={classes_to_import} name="classesToImport" value={ca.concreteActivityId} />
                {ca.educationTypeAbbrev}
            </label>
        </td>

        <td>
            {ca.educationTypeAbbrev}/{ca.order}, {ca.subjectVersionCompleteCode}
        </td>
        <td>
            {ca.teacherFullNames}
        </td>

        <td>
            {ca.weekDayAbbrev}
        </td>

        <td>
            {ca.beginTime}
        </td>

        <td>
            {ca.endTime}
        </td>
    </tr>
    {/each}
    </tbody>
</table>
{/if}


<button class="btn btn-success" on:click={import_activities} disabled={!canImport} class:btn-danger={!canImport}>
    {#if busy}
        Importing...
    {:else}
        Import
    {/if}
</button>


{#if result}
    {#if result.error}
        <div class="alert alert-danger" role="alert">
            {result.error}
        </div>
    {:else}
        <table class="table table-sm table-hover table-striped">
            <tbody>
            {#each result.users as item}
                <tr>
                    <td>{item.login}</td>
                    <td>{item.firstname}</td>
                    <td>{item.lastname}</td>
                    <td>{item.created}</td>
                </tr>
            {/each}
            </tbody>
        </table>
    {/if}
{/if}
