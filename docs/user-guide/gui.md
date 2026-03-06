## Graphical Interface

This is the user guide to BSP, the GUI that allows the user to remotely connect to their SLURM-compatible HPC and run jobs.

### Access

[Link to GUI](https://dane.anvilcloud.rcac.purdue.edu/)

### Registering for an Account

Registration requires a unique username, password, as well as your HPC information. We require the hostname, your username on your HPC, as well as your SSH key. All of this information is stored in an encrypted database on our server.

!!! note
    Your user credentials are actually the only data we store on our servers. Everything else is through a config file that lives on your HPC in your /home/<username>/.config/bsp/config.yaml. We made this decision because we do not want to host as minimal data as possible.

### Connecting to your HPC

As mentioned in the registration section, you will provide a unique username/password combo, as well as your HPC login information. When you click Register, we make a quick SSH connection to your HPC to determine that we can indeed connect.

The only software required for you to install on your HPC before you register is [UV](https://docs.astral.sh/uv/getting-started/installation/). When we run remote commands from the GUI onto your HPC, we use UV's functionality that can access our `bioinformatics-tools` package remotely from their repo.

!!! note "How we access our package on your HPC"
    We run the following command on your HPC:
    `$ uvx --from bioinformatics-tools ... (our CLI commands)`
    This allows us to not worry about installing or caching our library on your HPC system - UV does this for us!.

### Profile Page (Config)

This will first show you if we are able to successfully connect to your HPC/remote server. If so, you should see a green dot and a message "Connected to <hostname>".

The Config section just streams the contents of your `~/.config/bsp/config.yaml` file. You can edit these values on the GUI and it will update that config file on your server once you click Save Configuration. Conversely, you can update these values on your remote sever and when you refresh the page, the new values will be shown.

As of right now, on the GUI you cannot create new config variables; this functionality is only supported when you update the file on the cluster. The GUI only allows you to update existing variables. This will change in the future, but is this way for simplicity right now.

### Analyze Page

This page dynamically fetches any workflows we find in the system. The system uses a small data object to find workflows, and eventually users will be able to define their own workflows and the system will magically find them. For now, we have 2 small workflows: 1) margie and 2) CustomMicrobiome (small, test workflow).

When you run a workflow, you need to specify a genome (fasta) file that **is located on your remote server**. If this file does not exist **on your remote server**, you'll see an error message. Optionally, you can define an Output Directory, which should be at a writeable location on your server. If you do not specify anything, it will by default write to your home directory (~/<date-hour-minute-time>).

**What Happens When I Click Analyze?**

It'll simply run the workflow. Here's how:

1. We use `UVX --from` to provide your remote server with access to our CLI
2. Our workflows call containers from our own private container repo to control executables for each step
3. Our workflows reference databases **on your own server** in a standard location: (<prefix/databases/>). In the config file on your profile page, you'll need to specify your `database_location_prefix`
4. We use `snakemake --executor slurm` to control submitting jobs to SLURM.
5. We stream all the logs and information from your cluster to BSP so you can stay informed for each step.

Before running the workflow, we first check your individual or group sqlite3 database to determine if you have already ran the following information. This allows us to determine cache hits vs cache misses; we only run workflow steps if the job is a cache miss.

!!! important "Specifying your database"
    You specify the location you want your database in your profile page with the key: `main-database`. Please ensure this is in a location writeable for both you and your group member.