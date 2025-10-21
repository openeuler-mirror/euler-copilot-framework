FROM hub.oepkgs.net/neocopilot/framework_base:0.10.1-x86-test

ENV PYTHONPATH=/app
ENV TIKTOKEN_CACHE_DIR=/app/assets/tiktoken

COPY --chmod=550 ./ /app/
RUN chmod 766 /root

CMD ["uv", "run", "--no-sync", "--no-dev", "apps/main.py"]
