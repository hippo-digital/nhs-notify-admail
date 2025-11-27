import json
import sys
from pathlib import Path
from datetime import datetime
import argparse
from typing import Dict, List
import matplotlib.pyplot as plt
import seaborn as sns
from explainable_classifier import ExplainableClassifier, DocumentExtractor


def find_documents(data_dir: Path, category: str = None, limit: int = None) -> List[Dict]:
    documents = []
    categories = [category] if category else ["Business", "Advertising", "Unsure"]

    for cat in categories:
        cat_dir = data_dir / cat
        if not cat_dir.exists():
            print(f"Warning: Category directory not found: {cat_dir}")
            continue

        files = list(cat_dir.glob("*.docx")) + list(cat_dir.glob("*.pdf"))

        if limit:
            files = files[:limit]

        for file_path in files:
            documents.append({
                "path": file_path,
                "category": cat,
                "name": file_path.name
            })

    return documents

def create_confusion_matrix(results: List[Dict], output_dir: Path):
    categories = ["BUSINESS", "ADVERTISING", "UNSURE"]
    confusion_matrix = {}
    for actual_cat in categories:
        confusion_matrix[actual_cat] = {pred_cat: 0 for pred_cat in categories}
    for result in results:
        actual_category = result["actual_category"].upper()
        predicted_rating = result["predicted_rating"]

        if actual_category in confusion_matrix and predicted_rating in confusion_matrix[actual_category]:
            confusion_matrix[actual_category][predicted_rating] += 1
    total_predictions = len(results)
    correct_predictions = sum(
        confusion_matrix[cat][cat] for cat in categories
    )
    accuracy = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
    matrix_data = []
    for actual in categories:
        row = [confusion_matrix[actual].get(pred, 0) for pred in categories]
        matrix_data.append(row)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        matrix_data,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=categories,
        yticklabels=categories,
        ax=ax,
        cbar_kws={'label': 'Count'},
        square=True
    )

    ax.set_xlabel('Predicted Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('Actual Category', fontsize=12, fontweight='bold')
    ax.set_title(f'Confusion Matrix - Explainable Classifier\nAccuracy: {accuracy:.2f}%', fontsize=14, fontweight='bold', pad=20)

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_path = output_dir / f"confusion_matrix_{timestamp}.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\nConfusion matrix saved: {plot_path}")
    return {
        "confusion_matrix": confusion_matrix,
        "accuracy": accuracy,
        "total_predictions": total_predictions,
        "correct_predictions": correct_predictions
    }

def save_detailed_results(results: List[Dict], output_dir: Path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"batch_results_{timestamp}.json"

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "total_documents": len(results),
        "results": results
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results saved: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Batch Document Classifier with Confusion Matrix"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Path to data directory containing Business/Advertising/Unsure folders"
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
        "--output-dir",
        type=str,
        default="batch_results",
        help="Directory to save results and confusion matrix"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=["Business", "Advertising", "Unsure"],
        help="Process only specific category"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of documents per category"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="eu-west-2",
        help="AWS region for Bedrock"
    )

    args = parser.parse_args()

    # Setup paths
    script_dir = Path(__file__).parent
    data_dir = script_dir / args.data_dir

    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    # Locate prompt file
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
            print(f"Error: Could not find prompt file '{args.prompt}'")
            sys.exit(1)

        prompt_path = found_prompt

    # Create output directory
    output_dir = script_dir / args.output_dir
    output_dir.mkdir(exist_ok=True)

    # Find documents
    documents = find_documents(data_dir, args.category, args.limit)
    print(f"\nFound {len(documents)} documents to process")
    print(f"Prompt: {prompt_path.name}")
    print(f"Model: {args.model}")
    print(f"Category filter: {args.category or 'All'}")

    if not documents:
        print("No documents found to process!")
        sys.exit(1)

    classifier = ExplainableClassifier(
        prompt_file_path=str(prompt_path),
        model_id=args.model,
        region=args.region
    )

    results = []

    for i, doc in enumerate(documents, 1):
        print(f"\n[{i}/{len(documents)}] Processing: {doc['name']} (Actual: {doc['category']})")

        # Extract text
        text = DocumentExtractor.extract_text(doc["path"])
        if not text:
            print(f"Failed to extract text, skipping...")
            continue

        print(f"Extracted {len(text)} characters")

        try:
            print("Classifying...")
            features = classifier._extract_features(text)
            personalization = classifier._analyze_personalization(text, features)
            content_analysis = classifier._analyze_content(text, features, personalization)
            classification = classifier._classify_with_reasoning(text, features, personalization, content_analysis)

            rating = classification.get("rating", "UNKNOWN")
            confidence = classification.get("confidence", "unknown")
            primary_reason = classification.get("primary_reason", "")

            print(f"* Predicted: {rating} (confidence: {confidence})")

            results.append({
                "document_name": doc["name"],
                "actual_category": doc["category"],
                "predicted_rating": rating,
                "confidence": confidence,
                "primary_reason": primary_reason,
                "match": doc["category"].upper() == rating
            })

        except Exception as e:
            print(f"Error classifying: {e}")
            results.append({
                "document_name": doc["name"],
                "actual_category": doc["category"],
                "predicted_rating": "ERROR",
                "confidence": "none",
                "primary_reason": str(e),
                "match": False
            })

    print("Creating confusion matrix...")
    stats = create_confusion_matrix(results, output_dir)
    save_detailed_results(results, output_dir)

if __name__ == "__main__":
    main()
