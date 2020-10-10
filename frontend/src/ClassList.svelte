<script>
  import {push, link} from 'svelte-spa-router'
  let classes = fetch('/api/classes').then(res => res.json()).then(res => res['classes']);
</script>

{#await classes}
loading
{:then classes}
  {#each classes as clazz}
    <div class="card mb-2" style="position: initial">
          <div class="card-header">
              <div class="float-right">
                <a href="/task/add/{clazz.subject_abbr}" use:link title="Assign new task"><i class="fas fa-calendar-plus"></i></a>
                <a href="{clazz.csv_link}" title="Download CSV with results for all task"><i class="fas fa-file-csv"></i></a>
              </div>
              <button class="btn btn-link">
                <h5>{clazz.subject_abbr} {clazz.timeslot} {clazz.code} {clazz.teacher_username}</h5>
              </button>
          </div>
          <div> 
            <div class="card-body">
              {@html clazz.summary}
              <table class="table table-sm table-hover">
                <thead>
                  <tr>
                    <th>Login</th>
                    <th>Student</th>
                    {#each clazz.assignments as assignment}
                    <th class="more-hover">
                      <a href="{ assignment.task_link }">{ assignment.short_name }</a>
                      <div class="more-content">
                        {assignment.name}
                        <a href="/task/edit/{assignment.task_id}" use:link class="text-muted" title="Edit"><i class="fas fa-pen"></i></a>
                        <div>
                          <a href="{assignment.moss_link}" title="Send to MOSS"><i class="fas fa-check-double"></i></a>
                          <a href="{assignment.sources_link}" title="Download all source codes"><i class="fas fa-download"></i></a>
                          <a href="{assignment.csv_link}" title="Download CSV with results"><i class="fas fa-file-csv"></i></a>
                        </div>
                        <dl>
                          <dt>Assigned</dt>
                          <dd>
                            {assignment.assigned}
                          </dd>

                          <dt>Deadline</dt>
                          <dd>
                            {assignment.deadline}
                          </dd>

                          {#if assignment.max_points}
                          <dt>Max points</dt>
                          <dd>
                            {assignment.max_points} 
                          </dd>
                          {/if}
                        </dl>
                      </div>
                    </th>
                    {/each}
                  </tr>
                </thead>

                {#each clazz.students as student}
                <tr>
                  <td>{ student.username }</td>
                  <td>{ student.last_name } { student.first_name }</td>
                  {#each clazz.assignments.map(i => i.students[student.username]) as result}
                    <td>
                      {#if result.submits != 0}
                        <a href={result.link} style="color: {result.color}">
                          { isNaN(parseFloat(result.assigned_points)) ? '?' : result.assigned_points}
                        </a>
                      {/if}
                    </td>
                  {/each}
                </tr>
                {/each}
              </table>
            </div>
          </div>
      </div>
  {/each}
{:catch}
  Failed
{/await}
