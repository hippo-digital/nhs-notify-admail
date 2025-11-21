FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir \
    flask \
    flask-cors

COPY main.py ${LAMBDA_TASK_ROOT}/
COPY system_prompt.txt ${LAMBDA_TASK_ROOT}/
COPY core/ ${LAMBDA_TASK_ROOT}/core/
COPY services/ ${LAMBDA_TASK_ROOT}/services/
COPY api_wrapper.py ${LAMBDA_TASK_ROOT}/

ENTRYPOINT ["python", "api_wrapper.py"]

EXPOSE 8080
