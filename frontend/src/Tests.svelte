<style>
    :global(.tests .CodeMirror) {
      height: 200px !important;
      min-height: 200px !important;
    }
</style>
    

<script>
    import {fs, cwd, openedFiles} from './fs.js'
    import Editor from './Editor.svelte'
    import yaml from 'js-yaml';

    let loaded = false;
    $: tests = {};

    function create(name) {
        return {
            'name': name,
            'args': '',
            'files': {},
        }
    }

    function add_test() {
        const name = `test${Object.keys(tests).length}`
        tests[name] = create(name);
    }

    async function delete_test(name) {
        for(const path of Object.values(tests[name]['files'])) {
            fs.remove(path);
        }

        delete tests[name];
        tests = tests;
    }

    async function add_file(name, shown_name, file_name) {
        const path = `${name}.${file_name}`
        await fs.createFile(path);
        await fs.open(path, {'hide_tab': true});
        tests[name]['files'][shown_name] = '/' + path;
    }

    async function remove_file(name, file_name) {
        const path = tests[name]['files'][file_name];
        delete tests[name]['files'][file_name];
        await fs.remove(path);
    }

    async function load() {
        let newtests = {};
        for(const inode of $cwd) {
            if(inode.type != 'file') {
                continue;
            }

            async function add(name, x, file_name) {
                let test = newtests[name] = newtests[name] || create(name);
                test['files'][x] = '/' + file_name;
                await fs.open(file_name, {'hide_tab': true});
            }

            const parts = inode.name.split('.');
            const ext = parts[parts.length - 1];
            const name = parts[0];
            if(ext == 'out' || ext == 'in' || ext == 'err' && parts.length == 2) {
                await add(name, 'std' + parts[1], inode.name)
            } else if(parts.length >= 3) {
                const dir = parts[1];
                if(dir == 'file_in' || dir == 'file_out') {
                    await add(name, parts.slice(2).join('.'), inode.name);
                }
            }
        }

        if(await fs.open('tests.yml', {'hide_tab': true})) {
            const descs = yaml.load($openedFiles['/tests.yml'].content);

            for(const test of descs) {
                if(test.name) {
                    newtests[test.name] = newtests[test.name] || create(test.name);
                    if(test.args) {
                        newtests[test.name].args = test.args.join(' ')
                    }
                    newtests[test.name].title = test.title;
                }
            }
        }


        tests = newtests;
        loaded = true;
    }

    $: if(loaded) {
        save(tests);
    }

    async function save(tests) {
        let description = [];
        for(const [name, test] of Object.entries(tests)) {
            let data = {};
            if(test.args) {
                data.args = test.args.split(' ');
            }

            if(test.title) {
                data.title = test.title;
            }

            if(data) {
                description.push({name: name, ...data});
            }
        }

        if(!await fs.open('tests.yml', {hide_tab: true})) {
            await fs.createFile('tests.yml');
            await fs.open('tests.yml', {hide_tab: true});
        }
        $openedFiles['/tests.yml'].content = yaml.dump(description);
    }

    function file_sorter(a, b) {
        const stds = ['stdin', 'stdout', 'stderr'];
        const isStd = name => stds.indexOf(name) != -1;

        a = a[0];
        b = b[0];

        if(isStd(a) && isStd(b)) {
            return stds.indexOf(a) < stds.indexOf(b) ? -1 : 1;
        }
        
        if(isStd(a)) {
            return -1;
        }

        return 1;
    }

    load();
</script>

<div class="tests">
{#each Object.values(tests) as test}
    <h2>
        {test.name}

        {#each ['stdin', 'stdout', 'stderr'] as fd}
            {#if !test.files[fd]}
                <button on:click={add_file(test.name, fd, fd.replace('std', ''))} class="btn btn-sm btn-success mr-1">
                    <span class="iconify" data-icon="ant-design:plus-outlined"></span>
                    {fd}
                </button>
            {/if}
        {/each}

        <div class="btn-group" role="group" aria-label="Basic example">
            <input type="text" class="form-control form-control-sm" placeholder="Filename" bind:value={test.new_filename}>
        
            <button type="button" class="btn btn-sm btn-success text-nowrap" on:click={() => test.new_filename && add_file(test.name, test.new_filename, `file_in.${test.new_filename}`)}><span class="iconify" data-icon="ant-design:plus-outlined"></span>input</button>
            <button type="button" class="btn btn-sm btn-success text-nowrap" on:click={() => test.new_filename && add_file(test.name, test.new_filename, `file_out.${test.new_filename}`)}><span class="iconify" data-icon="ant-design:plus-outlined"></span>output</button>
        </div>

        <button class="btn btn-sm btn-danger" on:click={() => delete_test(test.name)}>
            <span class="iconify" data-icon="humbleicons:times"></span>
        </button>
    </h2>

    <div class="form-group row">
        <label class="col-sm-2 col-form-label">Title</label>
        <input type="text" class="form-control form-control-sm col-sm-10" bind:value={test.title}>
    </div>

    <div class="form-group row">
        <label class="col-sm-2 col-form-label">Program Arguments</label>
        <input type="text" class="form-control form-control-sm col-sm-10" bind:value={test.args}>
    </div>

    {#each Object.entries(test.files).sort(file_sorter) as [k, v]}
        <h3>
            {k}
            <button on:click={() => remove_file(test.name, k)} class="btn btn-sm btn-danger">
                <span class="iconify" data-icon="humbleicons:times"></span>
            </button>
        </h3>
        <Editor bind:value={$openedFiles[v].content} />
    {/each}


    <hr>
{/each}
<button on:click={add_test} class="btn btn-success">
    <span class="iconify" data-icon="ant-design:plus-outlined"></span>
    Add new test
</button>

</div>