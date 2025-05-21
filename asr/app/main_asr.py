from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil, os, traceback, time
from tempfile import NamedTemporaryFile
from whisper_handler import transcribe_audio
from jiwer import wer
import Levenshtein
import jieba  # 加入 jieba 斷詞

app = FastAPI()

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/")
async def read_index():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return FileResponse(os.path.join(static_dir, "index.html"))

def calculate_cer(reference: str, hypothesis: str) -> float:
    reference = reference.replace(" ", "")
    hypothesis = hypothesis.replace(" ", "")
    if len(reference) == 0:
        return 1.0 if len(hypothesis) > 0 else 0.0
    return Levenshtein.distance(reference, hypothesis) / len(reference)

def calculate_wer_chinese(reference: str, hypothesis: str) -> float:
    ref_words_list = list(jieba.cut(reference))
    hyp_words_list = list(jieba.cut(hypothesis))
    ref_words = " ".join(ref_words_list)
    hyp_words = " ".join(hyp_words_list)

    print(f"Reference segmentation: {ref_words_list}")
    print(f"Hypothesis segmentation: {hyp_words_list}")

    return wer(ref_words, hyp_words)

@app.post("/v1/audio/transcriptions")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    model: str = Form(...),
    answer_file: UploadFile = File(None)
):
    start_time = time.time()
    try:
        suffix = os.path.splitext(file.filename)[1]
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        text = transcribe_audio(tmp_path)

        # 讀取 txt 正確答案（若有上傳）
        correct_answer = ""
        cer_score = None
        wer_score = None

        if answer_file:
            correct_answer = (await answer_file.read()).decode("utf-8").strip()

            wer_score = calculate_wer_chinese(correct_answer, text)
            cer_score = calculate_cer(correct_answer, text)

        end_time = time.time()
        duration = round(end_time - start_time, 2)

        return JSONResponse(content={
            "檔案名稱": file.filename,
            "抄寫內容": text,
            "正確答案": correct_answer,
            "運行時長": f"{duration} 秒",
            "WER": round(wer_score, 4) if wer_score is not None else None,
            "CER": round(cer_score, 4) if cer_score is not None else None
        })

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="語音辨識失敗：" + str(e))
