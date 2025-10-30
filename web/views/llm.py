import os

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from common.models import Submit
from common.summary.summary import SUMMARY_RESULT_FILE_NAME
from web.views.utils import authenticate_submit_token_request


@csrf_exempt
def post_submit_summary_result(request, assignment_id, login, submit_num):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)

    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
    )

    authenticate_submit_token_request(request, submit)

    result_path = os.path.join(
        "submit_results",
        *submit.path_parts(),
    )

    os.makedirs(result_path, exist_ok=True)
    summary_file_path = os.path.join(result_path, SUMMARY_RESULT_FILE_NAME)

    with open(summary_file_path, "wb") as summary_file:
        summary_file.write(request.body)

    return JsonResponse({"status": "success"})
