// 환경 설정: 백엔드 API 주소.
// 내 컴퓨터(localhost/127.0.0.1)에서 열면 로컬 백엔드를, 그 외(배포)에서는 Render 주소를 쓴다.
const PRODUCTION_API_URL = "https://spoca-api.onrender.com/api";
const LOCAL_API_URL = "http://127.0.0.1:8000/api";

const isLocal = ["localhost", "127.0.0.1"].includes(location.hostname);

export const API_BASE_URL = isLocal ? LOCAL_API_URL : PRODUCTION_API_URL;
