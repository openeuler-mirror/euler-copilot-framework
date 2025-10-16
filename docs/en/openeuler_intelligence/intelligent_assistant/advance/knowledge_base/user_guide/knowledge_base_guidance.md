# witChainD User Guide – Knowledge Base Management

## 1. Overview

After the deployment of openEuler intelligence is completed, witChainD is integrated into the web page, allowing you to use witChainD for knowledge base management. Below is an introduction to the usage of witChainD.

1. Overview
2. Create Team
3. Create Asset Library
4. Upload Documents
5. Generate Dataset
6. Accuracy Test
7. Summary

## 2. Create Team

To create a new team, click "Create Team" to set up your own team. Enter the team name and team description in the corresponding fields, optionally set whether to make the team public, then click "Confirm".
![Create Team](./pictures/create_team.png)
After creating the team, the newly created team will be displayed on the witChainD page.
![Create Team Result](./pictures/create_team_result.png)

## 3. Create Asset Library

Click the newly created team to enter the **Team Asset Library Page**, then click "Create Asset Library".
![Team Asset Library](./pictures/team_asset_library.png)
Fill in information such as the asset library name and description.
![Create Team Asset Library](./pictures/create_team_asset_lib.png)
After clicking "Confirm", a prompt will pop up asking whether to import documents. You can choose to import documents directly, or enter the newly created asset library later to import documents.

After creating the team asset library, the newly created knowledge base will be displayed on the team page.
![Create Team Asset Library Result](./pictures/create_team_asset_lib_result.png)

## 4. Upload Documents

Click an asset library to enter the **Asset Library Page**, then click "Import Documents", select files and import them (multiple files can be selected for import).
![Import Asset Library Documents](./pictures/import_asset_library_documents.png)
After the import is completed, the newly imported documents will be displayed in the asset library and parsed. Once parsing is finished, you can perform related operations on the documents, such as using them to generate a dataset.

After successful parsing, click the document name to view the parsing status. You can also click "Reparse" to re-analyze the document, and set different parsing methods through the edit function.
![View Parsing Results](./pictures/view_parsing_results.png)

The parsing results are roughly as follows:
![Parsing Results](./pictures/parsing_results.png)

After uploading the documents, you can select a knowledge base to start a conversation in openEuler intelligence.
![Select Knowledge Base for Conversation](./pictures/select_knowledge_base_for_conversation.png)

The citation numbers in each answer match the citation sources on the right.
![Knowledge Base Conversation Citation Sources](./pictures/knowledge_base_conversation_citation_sources.png)

## Supplementary Chapters Below

These chapters are used to verify the effect and status of imported documents, helping developers optimize the system.

## 5. Generate Dataset

You can select imported document sets to generate a dataset. Check the documents needed for dataset generation and click "Generate Dataset".
![Generate Dataset](./pictures/generate_dataset.png)

Fill in relevant information and select required configurations, then click "Generate" to wait for the dataset generation in the **Dataset Management Page**.
![Generate Dataset Configuration](./pictures/generate_dataset_configuration.png)

You can click on a dataset name to view the dataset generation status. The results are roughly as follows:
![Dataset Results](./pictures/dataset_results.png)

## 6. Accuracy Test

For dataset evaluation, check the dataset and click **Generate**.
![Evaluate Dataset](./pictures/evaluate_dataset.png)
Fill in relevant evaluation information and configurations, then click "Confirm" to evaluate the selected dataset.

After the dataset evaluation is completed, you can click the test name to view the dataset test status. The results are roughly as follows:
![Dataset Evaluation Results](./pictures/dataset_evaluation_results.png)

## 7. Summary

Based on the above process, users can quickly get started with witChainD. Welcome to experience and explore more functional scenarios.
