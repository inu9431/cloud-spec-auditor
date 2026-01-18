from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

# settings.py에서 설정한 장고 로거 사용
logger = logging.getLogger('django')

# 커스텀한 에러가 있으면 그거 발생 없으면 장고에러 발생 양식만 지금이 양식으로 나옴
def custom_exception_handler(exc, context):
    """
    모든 API 예외를 가로채서 표준 응답 형식을 생성함
    """
    # 1. DRF의 기본 핸들러를 먼저 실행 (기본적인 에러 응답 객체를 생성함)
    response = exception_handler(exc, context)

    # 2. 알려진 예외(APIException 상속)인 경우
    if response is not None:
        # 우리가 정의한 default_code가 있으면 사용하고, 없으면 클래스명을 소문자로 사용
        code = getattr(exc, 'default_code', response.status_text.lower().replace(' ', '_'))

        response.data = {
            'status': 'error',
            'code': code,
            'message': response.data.get('detail', '오류가 발생했습니다.'),
        }

    # 3. 알려지지 않은 예외 (서버 내부 에러, 500 에러 등)
    else:
        # 로그에 에러 상세 내용 기록 (추적용)
        logger.error(f"정의되지 않은 예외 발생: {str(exc)}", exc_info=True)

        return Response({
            'status': 'error',
            'code': 'server_error',
            'message': '서버 내부에서 처리 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response