# Teacher's guide

## Task announcement
When you create a task and assign it to a class, you can configure special `announce` content, which
will be shown to the students before the start of the assignment. You can use it e.g. to tell the
students what should they prepare for.

To use announcement, you can add a **single** `<div>` block with the `announce` class to the main
`readme.md` Markdown file of the task. If you want to use Markdown inside the block, also add the
`markdown="1"` attribute to it.

Example:
```markdown
<div class="announce" markdown="1">
On Wednesday, your task will appear here. Please prepare by reading Chapter 5.
</div>

Your task is to ...
```

If you assigned this task to students to start on Wednesday 12:30, they would see **only** the text
`On Wednesday, your task...` before Wednesday 12:30. After this date, they will see the full content
of the readme (including the announce part).
