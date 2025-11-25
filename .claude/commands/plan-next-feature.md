# Plan next feature

Given the context files and what we have already built, which one do you think would be the next most intelligent step to build?

Think about dependencies: The next thing to build has any dependencies? If so, do we need to build these? If so, do these have dependencies too?

Use Supabase MCP to check the DB schema and data.
Use Supabase MCP to create and push migrations.
Use supabase's exported types when creating a new feature.
Remember that we are using Supabase cloud hosted, not a local instance.

As the first part of the implementation, create a dedicated branch with the feature name/description
