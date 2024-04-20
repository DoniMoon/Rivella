from openai import OpenAI
from typing import Tuple, List
import os
import json
import openreview
import openai

def get_openai_client() -> OpenAI:
    client = OpenAI()
    return client

def parse_pdf(client:OpenAI, pdf_file_path:str) -> Tuple[str, str, openai.types.beta.assistant.Assistant, str]:
    # call gpt-4 and get summary of the papers.
    # return 1-line summary, and keyword, openai assistant, file_id

    file_obj = client.files.create(
        file=open(pdf_file_path, "rb"),
        purpose="assistants"
    )
    reviewer = client.beta.assistants.create(
        instructions="You are reviewing the academic paper. You will be asked to critic the paper in the perspective of diverse reviewer.",
        name="Paper reviewer",
        tools=[{"type": "file_search"}],
        model="gpt-4-turbo",
    )
    # empty_thread = client.beta.threads.create()
    # thread_message = client.beta.threads.messages.create(
    #     empty_thread.id,
    #     role="user",
    #     content="First, extract main keyword and one-line summary from this paper. Give me a json object with field names, 'keyword' and 'summary'.",
    #     attachments=[{'file_id':file_obj.id,'tools':[{"type": "file_search"}]}],
    # )
    # run = client.beta.threads.runs.create(
    #     thread_id=empty_thread.id,
    #     assistant_id=reviewer.id,
    # )
    # run_steps = client.beta.threads.runs.steps.list(
    #     thread_id=empty_thread.id,
    #     run_id=run.id
    # )
    # messages = client.beta.threads.messages.list(
    #     thread_id=empty_thread.id,
    #     run_id = run.id
    # )
    # response_text = messages.to_dict()['data'][0]['content'][0]['text']['value']
    # try:
    #     response_dict = json.loads(response_text.split("```json\n")[-1].split("\n```")[0])
    # except:
    #     return response_text
    # summary = response_dict['summary']
    # keyword = response_dict['keyword']
    summary = "Addresses the issue of informed answers in question generation for educational assessments by proposing an indirect question generation method that can validate knowledge without relying on direct recognition of key terms."
    keyword = 'Question Generation'
    return summary, keyword, reviewer, file_obj.id

def get_sample_reviews(summary:str, keyword:str) -> List[str]:
    # 
    client = openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=os.environ.get('openreview_id'),
        password=os.environ.get('openreview_pw'),
    )
    results = []
    notes = client.search_notes(summary,source='reply')
    if len(notes) < 3:
        notes = client.search_notes(keyword,source='reply')
    for note in notes[:3]:
        note.content.pop('first_time_reviewer', None)
        results.append(str(note.content))
    return results

