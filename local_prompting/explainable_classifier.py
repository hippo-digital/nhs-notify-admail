"""
The classifier breaks down the analysis into stages:
1. Document Feature Extraction
2. Personalization Analysis
3. Content Analysis
4. Eligibility Determination
5. Detailed Reasoning and Recommendations
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
import argparse
from typing import Dict, Optional
import boto3
from botocore.exceptions import ClientError
from docx import Document
import PyPDF2

class DocumentExtractor:
    @staticmethod
    def extract_from_docx(file_path: Path) -> Optional[str]:
        try:
            doc = Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text.strip()
        except Exception as e:
            print(f"Error extracting text from {file_path.name}: {e}")
            return None

    @staticmethod
    def extract_from_pdf(file_path: Path) -> Optional[str]:
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = []
                for page in pdf_reader.pages:
                    text.append(page.extract_text())
                return "\n".join(text).strip()
        except Exception as e:
            print(f"Error extracting text from {file_path.name}: {e}")
            return None

    @classmethod
    def extract_text(cls, file_path: Path) -> Optional[str]:
        suffix = file_path.suffix.lower()
        if suffix == ".docx":
            return cls.extract_from_docx(file_path)
        elif suffix == ".pdf":
            return cls.extract_from_pdf(file_path)
        else:
            print(f"Unsupported file type: {suffix}")
            return None


class ExplainableClassifier:
    def __init__(self, prompt_file_path: str, model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0", region: str = "eu-west-2"):
        self.region = region
        self.model_id = model_id
        self.bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=self.region
        )
        try:
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            last_error = None
            for encoding in encodings:
                try:
                    with open(prompt_file_path, "r", encoding=encoding) as f:
                        self.system_prompt = f.read()
                    print(f"Loaded prompt from: {Path(prompt_file_path).name} (encoding: {encoding})")
                    break
                except UnicodeDecodeError as e:
                    last_error = e
                    continue
            else:
                print(f"Error: Could not decode prompt file with any supported encoding")
                if last_error:
                    print(f"Last error: {last_error}")
                sys.exit(1)

        except FileNotFoundError:
            print(f"Error: Prompt file not found: {prompt_file_path}")
            sys.exit(1)

    def analyze_document(self, document_text: str, document_name: str) -> Dict:
        print(f"Analyzing: {document_name}")
        print("Step 1: Extracting document features...")
        features = self._extract_features(document_text)
        self._print_step_result("Features Extracted", features)
        print("\nStep 2: Analyzing personalization...")
        personalization = self._analyze_personalization(document_text, features)
        self._print_step_result("Personalization Analysis", personalization)
        print("\nStep 3: Analyzing content uniformity and purpose...")
        content_analysis = self._analyze_content(document_text, features, personalization)
        self._print_step_result("Content Analysis", content_analysis)
        print("\nStep 4: Determining eligibility classification...")
        classification = self._classify_with_reasoning(document_text, features, personalization, content_analysis)
        self._print_step_result("Final Classification", classification)
        print("\nStep 5: Generating improvement recommendations...")
        recommendations = self._generate_recommendations(document_text, classification)
        self._print_step_result("Recommendations", recommendations)
        result = {
            "document_name": document_name,
            "timestamp": datetime.now().isoformat(),
            "analysis": {
                "features": features,
                "personalization": personalization,
                "content": content_analysis,
                "classification": classification,
                "recommendations": recommendations
            },
            "summary": {
                "rating": classification.get("rating", "UNKNOWN"),
                "confidence": classification.get("confidence", "unknown"),
                "primary_reason": classification.get("primary_reason", ""),
            }
        }
        return result

    def _extract_features(self, text: str) -> Dict:
        prompt = f"""Analyze this letter and extract key features. Look for:

1. NHS numbers or unique identifiers
2. Double bracket merge fields (())
3. Personalization elements (names, addresses, salutations)
4. Appointment details or dates
5. Medical conditions or treatments mentioned
6. Call to action statements
7. Contact information or response methods
8. Purpose of the letter

Letter text:
{text}

Provide your analysis as a JSON object with these keys:
- has_nhs_number: boolean
- has_merge_fields: boolean (look for (()) patterns)
- personalization_elements: list of strings (what's personalized)
- has_appointment_details: boolean
- mentions_medical_conditions: boolean
- call_to_action: string (the actual CTA text or "None found")
- purpose: string (brief description)
- key_phrases: list of important phrases that indicate targeting type

Return ONLY valid JSON, no other text."""

        response = self._invoke_model(prompt)
        return self._parse_json_response(response, "feature extraction")

    def _analyze_personalization(self, text: str, features: Dict) -> Dict:
        prompt = f"""Based on these extracted features, analyze the personalization level:

Features found:
{json.dumps(features, indent=2)}

Letter text:
{text}

Determine:
1. Is this SURFACE personalization only (name/address in header/salutation)?
2. Is this CONTENT personalization (NHS numbers, (()), individual medical data)?
3. What specific evidence supports your determination?
4. How does this affect AdMail eligibility?

Reference the personalization hierarchy:
- Surface: Name/address only, doesn't affect content uniformity
- Content: NHS numbers, merge fields (()), individual conditions, unique data

Return as JSON:
- personalization_type: "surface_only" | "content" | "none"
- evidence: list of specific examples from the text
- impact_on_eligibility: "disqualifies" | "neutral" | "supports"
- explanation: detailed reasoning

Return ONLY valid JSON, no other text."""

        response = self._invoke_model(prompt)
        return self._parse_json_response(response, "personalization analysis")

    def _analyze_content(self, text: str, features: Dict, personalization: Dict) -> Dict:
        prompt = f"""Analyze the content uniformity and purpose of this letter.

Features:
{json.dumps(features, indent=2)}

Personalization:
{json.dumps(personalization, indent=2)}

Letter text:
{text}

Determine:
1. Is the core message uniform (same for all recipients)?
2. Is the purpose promotional/informational or transactional?
3. Is this individual targeting or group/cohort targeting?
4. What Royal Mail criteria apply?

Return as JSON:
- content_uniformity: "uniform" | "variable" | "mixed"
- uniformity_explanation: string
- purpose_type: "promotional" | "informational" | "transactional" | "mixed"
- targeting_type: "individual" | "group" | "cohort" | "unclear"
- targeting_evidence: list of specific quotes
- applicable_royal_mail_criteria: list of criteria that apply

Return ONLY valid JSON, no other text."""

        response = self._invoke_model(prompt)
        return self._parse_json_response(response, "content analysis")

    def _classify_with_reasoning(self, text: str, features: Dict, personalization: Dict, content: Dict) -> Dict:
        prompt = f"""Based on all the analysis, determine the final AdMail eligibility rating.

Features:
{json.dumps(features, indent=2)}

Personalization:
{json.dumps(personalization, indent=2)}

Content Analysis:
{json.dumps(content, indent=2)}

Apply the decision rules:
- NHS number present → BUSINESS (99% of cases)
- Double brackets (()) → BUSINESS (99% of cases)
- Individual medical conditions/treatments → BUSINESS
- Surface personalization + uniform content → UNSURE or ADVERTISING
- Group campaign + no content personalization → ADVERTISING
- Ambiguous cases → UNSURE

Return as JSON:
- rating: "BUSINESS" | "UNSURE" | "ADVERTISING"
- confidence: "high" | "medium" | "low"
- primary_reason: main reason for this rating
- supporting_reasons: list of additional supporting factors
- contradicting_factors: list of factors that might suggest different rating
- decision_logic: step-by-step explanation of how you reached this rating

Return ONLY valid JSON, no other text."""

        response = self._invoke_model(prompt)
        return self._parse_json_response(response, "classification")

    def _generate_recommendations(self, text: str, classification: Dict) -> Dict:
        rating = classification.get("rating", "UNKNOWN")

        prompt = f"""Generate specific, actionable recommendations to improve this letter.

Current Classification:
{json.dumps(classification, indent=2)}

Letter text:
{text}

Provide recommendations in these categories:
1. Structural changes (quote actual problematic text and suggest replacements)
2. Call to action improvements (analyze current CTA strength)
3. Content improvements (make message more uniform if needed)
4. Design best practices (layout, QR code placement, etc.)

If rating is BUSINESS:
- How to convert to ADVERTISING (remove personalization, make uniform)

If rating is UNSURE:
- How to clarify and strengthen for ADVERTISING
- What needs to change to remove ambiguity

If rating is ADVERTISING:
- How to optimize effectiveness (CTA, layout, clarity)

Return as JSON:
- structural_changes: list of objects with keys: issue, current_text, suggested_change
- cta_improvements: object with keys: current_cta, strength, suggested_cta, rationale
- content_improvements: list of specific changes
- design_recommendations: list of layout/design suggestions
- priority_actions: list of top 3-5 most impactful changes

Return ONLY valid JSON, no other text."""

        response = self._invoke_model(prompt)
        return self._parse_json_response(response, "recommendations")

    def _invoke_model(self, user_prompt: str) -> str:
        messages = [{"role": "user", "content": [{"text": user_prompt}]}]

        inference_config = {
            "temperature": 0.1,
            "topP": 0.5,
            "maxTokens": 4096,
        }

        try:
            response = self.bedrock_runtime.converse(
                modelId=self.model_id,
                system=[{"text": self.system_prompt}],
                messages=messages,
                inferenceConfig=inference_config,
            )

            # Extract text from response
            response_message = response["output"]["message"]
            text_block = next(
                (content for content in response_message["content"] if "text" in content),
                None
            )

            if text_block:
                return text_block["text"]
            else:
                return "{\"error\": \"No text in response\"}"

        except ClientError as e:
            print(f"Error calling Bedrock: {e}")
            return f"{{\"error\": \"{str(e)}\"}}"

    def _parse_json_response(self, response: str, step_name: str) -> Dict:
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            response = response.strip()

            # Try to parse
            return json.loads(response)
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON in {step_name}: {e}")
            print(f"Response was: {response[:200]}...")
            return {"error": f"JSON parse error in {step_name}", "raw_response": response[:500]}

    def _print_step_result(self, title: str, data: Dict):
        print(f"\n{title}:")
        print(json.dumps(data, indent=2))

def save_analysis_report(result: Dict, output_file: Path):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Detailed analysis report saved to: {output_file}")

def print_summary(result: Dict):
    print(f"\nDocument: {result['document_name']}")
    print(f"Rating: {result['summary']['rating']}")
    print(f"Confidence: {result['summary']['confidence']}")
    print(f"\nPrimary Reason:")
    print(f"{result['summary']['primary_reason']}")

    classification = result['analysis']['classification']
    if 'supporting_reasons' in classification:
        print(f"\nSupporting Factors:")
        for reason in classification['supporting_reasons']:
            print(f"* {reason}")

    recommendations = result['analysis']['recommendations']
    if 'priority_actions' in recommendations:
        print(f"\nTop Priority Actions:")
        for i, action in enumerate(recommendations['priority_actions'][:5], 1):
            print(f"{i}. {action}")

def main():
    parser = argparse.ArgumentParser(
        description="Explainable Document Classifier for NHS AdMail Analysis"
    )
    parser.add_argument(
        "--document",
        type=str,
        default="data/Unsure/NHS Flu Letter.docx",
        help="Path to document file (.docx or .pdf) to analyze"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="revised_system_prompt.txt",
        help="Path to system prompt file"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="amazon.nova-pro-v1:0",
        help="Bedrock model ID to use"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for detailed analysis report (JSON)"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="eu-west-2",
        help="AWS region for Bedrock"
    )

    args = parser.parse_args()

    # Locate document file
    doc_path = Path(args.document)
    if not doc_path.exists():
        print(f"Error: Document file not found: {doc_path}")
        sys.exit(1)

    # Locate prompt file
    script_dir = Path(__file__).parent
    prompt_path = Path(args.prompt)
    if not prompt_path.is_absolute():
        possible_prompts = [
            script_dir / args.prompt,
            script_dir.parent / "src/backend/bedrock-prompt-messager" / args.prompt,
            prompt_path,
        ]

        found_prompt = None
        for p in possible_prompts:
            if p.exists():
                found_prompt = p
                break

        if not found_prompt:
            print(f"Error: Could not find prompt file '{args.prompt}'. Tried:")
            for p in possible_prompts:
                print(f"  - {p}")
            sys.exit(1)

        prompt_path = found_prompt

    # Extract document text
    print(f"Extracting text from: {doc_path.name}")
    text = DocumentExtractor.extract_text(doc_path)
    if not text:
        print("Failed to extract text from document")
        sys.exit(1)

    print(f"Extracted {len(text)} characters\n")

    classifier = ExplainableClassifier(
        prompt_file_path=str(prompt_path),
        model_id=args.model,
        region=args.region
    )
    result = classifier.analyze_document(text, doc_path.name)
    print_summary(result)
    if args.output:
        output_path = Path(args.output)
        save_analysis_report(result, output_path)
    else:
        output_dir = script_dir / "analysis_reports"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"analysis_{doc_path.stem}_{timestamp}.json"
        save_analysis_report(result, output_file)

if __name__ == "__main__":
    main()