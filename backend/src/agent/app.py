# mypy: disable - error - code = "no-untyped-def,misc"
import pathlib
import traceback
from fastapi import FastAPI, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger
from agent.logger import setup_logger, log_request_details
from agent.configuration import Configuration, load_available_models_from_env

# Define the FastAPI app
app = FastAPI(docs_url=None, redoc_url=None)
setup_logger()

# 添加获取模型列表的API端点
@app.get("/api/models")
async def get_available_models():
    """获取可用的LLM模型列表"""
    try:
        # 直接从环境变量加载模型列表
        models = load_available_models_from_env()
        models_data = [
            {
                "model_id": model.model_id,
                "display_name": model.display_name,
                "icon": model.icon,
                "icon_color": model.icon_color
            }
            for model in models
        ]
        logger.info(f"返回模型列表: {models_data}")
        return JSONResponse(content={"models": models_data})
    except Exception as e:
        logger.error(f"获取模型列表失败: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            content={"error": "获取模型列表失败", "details": str(e)},
            status_code=500
        )

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        # 记录请求基本信息
        logger.info(f"收到用户请求：{request.method} {request.url}")

        # # 拦截对文档端点的访问
        # if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        #     logger.warning(f"已拒绝该请求：{request.url}")
        #     return Response(status_code=404)

        # 如果是POST请求且有body，记录详细信息
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            if body:
                try:
                    import json
                    body_data = json.loads(body.decode())
                    log_request_details(body_data)
                except:
                    log_request_details(body.decode())
    except Exception as e:
        logger.error(f"记录请求日志时出错: {str(e)}")
        logger.error(traceback.format_exc())

    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"处理请求时出错: {str(e)}")
        logger.error(traceback.format_exc())
        raise


# def create_frontend_router(build_dir="../frontend/dist"):
#     """创建一个路由来服务React前端.
#
#     Args:
#         build_dir: 相对于此文件的React构建目录的路径.
#
#     Returns:
#         服务于前端的Starlette应用程序.
#     """
#     build_path = pathlib.Path(__file__).parent.parent.parent / build_dir
#
#     if not build_path.is_dir() or not (build_path / "index.html").is_file():
#         logger.info(
#             f"WARN: 前端构建目录在{build_path}处未找到或不完整 . 服务前端可能会失败."
#         )
#         # Return a dummy router if build isn't ready
#         from starlette.routing import Route
#
#         async def dummy_frontend(request):
#             return Response(
#                 "前端未构建，在前端目录中运行“npm运行构建”.",
#                 media_type="text/plain",
#                 status_code=503,
#             )
#
#         return Route("/{path:path}", endpoint=dummy_frontend)
#
#     return StaticFiles(directory=build_path, html=True)
#
#
# app.mount(
#     "/app",
#     create_frontend_router(),
#     name="frontend",
# )
