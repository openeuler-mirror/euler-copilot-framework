# MCP Service Guide

## 1. Overview

The current version of openEuler intelligence has enhanced support for MCP. The usage process is mainly divided into the following steps:

1. Register MCP
2. Install MCP
3. Activate MCP and load configuration files
4. Build Agent based on the activated MCP
5. Test Agent
6. Publish Agent
7. Use Agent

> **Note**:
>
> - Registration, installation, and activation of MCP require administrator privileges
> - Building, testing, publishing, and using Agent are ordinary user privilege operations
> - All Agent-related operations must be performed based on the activated MCP

## 2. Registration, Installation and Activation of MCP

The following process uses an administrator account as an example to demonstrate the complete management process of MCP:

1. **Register MCP**
   Register MCP to the openEuler intelligence system through the "MCP Registration" button in the plugin center
   ![mcp register button](pictures/regeister_mcp_button.png)

   Clicking the button pops up the registration window (the default configurations for SSE and STDIO are as follows):
   ![sse register window](pictures/sse_mcp_register.png)
   ![stdio register window](pictures/stdio_mcp_register.png)

   Taking SSE registration as an example, fill in the configuration information and click "Save"
   ![fill in mcp configuration file](pictures/add_mcp.png)

2. **Install MCP**

   > **Note**: Before installing STDIO, you can adjust service dependency files and permissions in the `/opt/copilot/semantics/mcp/template` directory on the corresponding container or server

   Click the "Install" button on the registered MCP card to install
   ![mcp install button](pictures/sse_mcp_intstalling.png)

3. **View MCP Tools**
   After successful installation, click the MCP card to view the tools supported by this service
   ![mcp service tools](pictures/mcp_details.png)

4. **Activate MCP**
   Click the "Activate" button to enable the MCP service
   ![mcp activate button](pictures/activate_mcp.png)

## 3. Creation, Testing, Publishing and Using of Agent Applications

The following operations can be completed by ordinary users, and all operations must be performed based on the activated MCP:

1. **Create Agent Application**
   Click the "Create Application" button in the application center
   ![create agent application](pictures/create_app_button.png)

2. **Configure Agent Application**
   After successful creation, click the application card to enter the details page, where you can modify the application configuration information
   ![modify agent application configuration](pictures/edit_Agent_app_message.png)

3. **Associate MCP**
   Click the "Add MCP" button, select the activated MCP from the list that pops up on the left to associate
   ![add mcp](pictures/add_mcp_button.png)
   ![mcp list](pictures/add_mcp.png)

4. **Test Agent Application**
   After completing MCP association and information configuration, click the "Test" button in the lower right corner to perform functional testing
   ![test agent application](pictures/test_mcp.png)

5. **Publish Agent Application**
   After passing the test, click the "Publish" button in the lower right corner to publish the application
   ![publish agent application](pictures/publish_app.png)

6. **Use Agent Application**
   The published application will be displayed in the application market, double-click to use
   ![use agent application](pictures/click_and_use.png)

   Agent applications have two usage modes:

   - **Automatic Mode**: Operations are executed automatically without manual user confirmation
     ![automatic use agent application](pictures/chat_with_auto_excute.png)

   - **Manual Mode**: Risks are prompted before execution, and execution requires user confirmation
     ![manual use agent application](pictures/chat_with_not_auto_excute.png)

## 4. Summary

Through the above process, users can build and use customized Agent applications based on MCP. Welcome to experience and explore more functional scenarios.
