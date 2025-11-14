# Specification Document for Chown Command MCP (Management Control Program)

## 1. Service Introduction
This service is an MCP (Management Control Program) based on the `chown` command, designed to change the owner and group of files or directories. Its core function is to modify the specified file or directory's owner and associated group to meet permission management and resource allocation requirements.

## 2. Core Tool Information
| Tool Name | Tool Function | Core Input Parameters | Key Return Content |
| ---- | ---- | ---- | ---- |
| `chown_change_owner_tool` | Change the owner and group of a file or directory | - `host`: Remote hostname/IP (optional for local operations)<br>- `owner_group`: File owner and associated group (required, cannot be empty)<br>- `file`: Path of the target file to modify (required, cannot be empty) | Boolean value indicating whether the operation was successful |

## 3. To-be-developed Requirements
