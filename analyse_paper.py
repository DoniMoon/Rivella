from openai import OpenAI
from typing import Tuple, List
import os
import json
import openreview
import openai
import random

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
    empty_thread = client.beta.threads.create()
    thread_message = client.beta.threads.messages.create(
        empty_thread.id,
        role="user",
        content="First, extract main keyword and one-line summary from this paper. Give me a json object with field names, 'keyword' and 'summary'.",
        attachments=[{'file_id':file_obj.id,'tools':[{"type": "file_search"}]}],
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=empty_thread.id, assistant_id=reviewer.id
    )
    messages = client.beta.threads.messages.list(
        thread_id=empty_thread.id,
        run_id = run.id
    )
    response_text = messages.to_dict()['data'][0]['content'][0]['text']['value']
    try:
        response_dict = json.loads(response_text.split("```json\n")[-1].split("\n```")[0])
    except:
        return response_text
    summary = response_dict['summary']
    keyword = response_dict['keyword']
    # summary = "Addresses the issue of informed answers in question generation for educational assessments by proposing an indirect question generation method that can validate knowledge without relying on direct recognition of key terms."
    # keyword = 'Question Generation'
    return summary, keyword, reviewer, file_obj.id

def classify_review(client: OpenAI, assistant: openai.types.beta.assistant.Assistant, review) -> str:
    if False:
        thread = client.beta.threads.create(
            # Create a thread and attach the file to the message
            messages=[
                {
                    "role": "user",
                    "content": "Classify the following review: " + str(review.content),
                }
            ]
        )

        run = openai_client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=assistant.id
        )

        messages = list(openai_client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
        value = messages[0].content[0].text.value

        score = value.strip().split(' ')[-1]
    else:
        score = ['favorable', 'skeptical', 'aggressive'][random.randint(0,2)]
    assert score in ['favorable', 'skeptical', 'aggressive']
    return score

def get_meta_reviewer(client: OpenAI) -> openai.types.beta.assistant.Assistant:
    assistant = client.beta.assistants.create(
        name="Meta Reviewer",
        instructions="""
      You are an expert in classifying the paper reviews.
      Please classify whether the following review is skeptical, favorable, or aggressive.
      Score each dimension from 1 to 10. Explain in detail why you thought like that.
      The followings are example output formats.

      Example Output: [skeptical: 6], [favorable: 3], [aggressive: 4].
      Thoughts: [Thoughts for skeptical: ...], [Thoughts for favorable: ...], [Thoughts for aggressive: ...].
      Final Classification: skeptical

      Example Output: [skeptical: 3], [favorable: 8], [aggressive: 5].
      Thoughts: [Thoughts for skeptical: ...], [Thoughts for favorable: ...], [Thoughts for aggressive: ...].
      Final Classification: favorable

      Example Output: [skeptical: 3], [favorable: 2], [aggressive: 7].
      Thoughts: [Thoughts for skeptical: ...], [Thoughts for favorable: ...], [Thoughts for aggressive: ...].
      Final Classification: aggressive
        """,
        model="gpt-4-turbo",
    )
    return assistant


def is_review(note) -> bool:
    return note.replyto is not None and any(['Official_Review' in inv for inv in note.invitations])

def get_sample_reviews(openai_client: OpenAI, summary:str, keyword:str):
    meta_reviewer = get_meta_reviewer(openai_client)

    #
    client = openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=os.environ.get('openreview_id'),
        password=os.environ.get('openreview_pw'),
    )
    # for skp, fav, aggr
    res_notes = [[], [], []]
    #XXX kmkim: return pdfs with notes
    pdfs = [[], [], []]

    notes = client.search_notes(summary,source='reply',limit=20)
    if len(notes) < 3:
        notes += client.search_notes(keyword,source='reply',limit=20)

    for note in notes:
        if is_review(note):
            note.content.pop('first_time_reviewer', None)
            #results.append(str(note.content))
            #XXX return the objects
            #results.append(note)
            try:
                pdf = client.get_pdf(note.forum)
                score = classify_review(openai_client, meta_reviewer, note)
                if score == 'skeptical':
                    res_notes[0].append(str(note))
                    pdfs[0].append(pdf)
                elif score == 'favorable':
                    res_notes[1].append(str(note))
                    pdfs[1].append(pdf)
                elif score == 'aggressive':
                    res_notes[2].append(str(note))
                    pdfs[2].append(pdf)
                else:
                    raise ValueError('Invalid score')
            except:
                pass
            # at most 3 per each category
            if len(res_notes[0]) == 3 and len(res_notes[1]) == 3 and len(res_notes[2]) == 3:
                break
        #pdfs.append(client.get_pdf(note.forum))
    #return [str(n) for n in notes], pdfs
    return res_notes, pdfs

def get_reviews(client:OpenAI, reviewer:openai.types.beta.assistant.Assistant, reviews: List[str],fid: str, pdfs: List[str],user_request:str='') -> str:
    review_thread = client.beta.threads.create()
    pdf_ids = []
    for pdf in pdfs:
        file_obj = client.files.create(
            file=open(pdf, "rb"),
            purpose="assistants"
        )
        pdf_ids.append(file_obj.id)
    pdf_ids.append(fid)
    thread_message = client.beta.threads.messages.create(
        review_thread.id,
        role="user",
        content=f"Generate a review for the paper. {user_request} Here is the examples of related reviews. Each review corresponds to a given file. " + '\n\n'.join(['Review for paper' + str(i+1) + ':\n' + r for i, r in enumerate(reviews)]) + '\nReview for paper 4:\n',
        attachments=[{'file_id':id,'tools':[{"type": "file_search"}]} for id in pdf_ids],
    )
    run = client.beta.threads.runs.create_and_poll(
        thread_id=review_thread.id, assistant_id=reviewer.id
    )
    messages = client.beta.threads.messages.list(
        thread_id=review_thread.id,
        run_id = run.id
    )
    response_text = messages.to_dict()['data'][-1]['content'][-1]['text']['value']
    return response_text

