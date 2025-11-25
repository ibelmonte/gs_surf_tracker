# Test feature

If full test requested then test the full code base. Otherwise, if a valid feature is mentioned then test that feature, if not then test the most recent feature developed.
When testing a feature, test all of its functionalities, routes, entities and screens, both using valid and invalid data to check for consistent and coherent error messages.

# How to test

Run a local development server on port 4000, if a previous development server was running on that port then just kill it.
Use the browser to test the functionality just written. You'll find a valid username and password in the secrets folder.
Use the Supabase's MCP to check the database schema, data and logs.
