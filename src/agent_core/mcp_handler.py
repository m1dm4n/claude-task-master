import logging
from typing import Optional, Dict, Any
from fastmcp import FastMCP

from ..data_models import Tool, ToolOutput


logger = logging.getLogger(__name__)


class MCPHandler:
    """
    Manages the lifecycle of the FastMCP server and handles interactions
    with MCP tools and resources.
    """

    def __init__(self):
        """
        Initialize MCPHandler.
        """
        self.mcp_server: Optional[FastMCP] = None
        logger.info("MCPHandler initialized.")

    async def start_mcp_server(self, host: str = "127.0.0.1", port: int = 8000):
        """Starts the FastMCP server."""
        if self.mcp_server:
            logger.info("MCP server already running.")
            return

        self.mcp_server = FastMCP(
            server_name="devtask-ai-assistant",
            host=host,
            port=port,
            description="DevTask AI Assistant MCP Server"
        )
        try:
            await self.mcp_server.start()
            logger.info(f"MCP server started on {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            self.mcp_server = None
            raise

    async def stop_mcp_server(self):
        """Stops the FastMCP server."""
        if self.mcp_server:
            try:
                await self.mcp_server.stop()
                logger.info("MCP server stopped.")
            except Exception as e:
                logger.error(f"Error stopping MCP server: {e}")
            finally:
                self.mcp_server = None
        else:
            logger.info("MCP server is not running.")

    def register_mcp_tool(self, tool: Tool):
        """Registers a tool with the MCP server."""
        if self.mcp_server:
            # MCP server expects a dict, convert Pydantic model to dict
            tool_dict = tool.model_dump(mode='json')
            self.mcp_server.register_tool(tool_dict)
            logger.info(f"Registered MCP tool: {tool.name}")
        else:
            logger.warning("MCP server not running. Cannot register tool.")

    def register_mcp_resource(self, uri: str, content: Any, content_type: str):
        """Registers a resource with the MCP server."""
        if self.mcp_server:
            self.mcp_server.register_resource(uri, content, content_type)
            logger.info(f"Registered MCP resource: {uri}")
        else:
            logger.warning("MCP server not running. Cannot register resource.")

    async def use_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> ToolOutput:
        """Executes a tool on a registered MCP server."""
        if not self.mcp_server:
            raise RuntimeError("MCP server is not running.")
        try:
            result = await self.mcp_server.use_tool(server_name, tool_name, arguments)
            return ToolOutput(stdout=result.get('stdout'), stderr=result.get('stderr'), exit_code=result.get('exit_code', 0), result=result.get('result'), error=result.get('error'))
        except Exception as e:
            logger.error(f"Error using MCP tool '{tool_name}' on server '{server_name}': {e}")
            return ToolOutput(exit_code=1, stderr=str(e), error=str(e))

    async def access_mcp_resource(self, server_name: str, uri: str) -> Any:
        """Accesses a resource on a registered MCP server."""
        if not self.mcp_server:
            raise RuntimeError("MCP server is not running.")
        try:
            return await self.mcp_server.access_resource(server_name, uri)
        except Exception as e:
            logger.error(f"Error accessing MCP resource '{uri}' on server '{server_name}': {e}")
            raise