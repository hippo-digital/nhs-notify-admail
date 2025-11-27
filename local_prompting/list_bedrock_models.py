import argparse
import boto3
from botocore.exceptions import ClientError

def list_available_models(region="eu-west-2"):
    try:
        bedrock = boto3.client(service_name="bedrock", region_name=region)

        print(f"\nQuerying Bedrock models in region: {region}")

        response = bedrock.list_foundation_models()
        models_by_provider = {}
        for model in response.get('modelSummaries', []):
            provider = model.get('providerName', 'Unknown')
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            models_by_provider[provider].append(model)

        # Print models by provider
        for provider in sorted(models_by_provider.keys()):
            print(f"\n{provider}")

            for model in models_by_provider[provider]:
                model_id = model.get('modelId', 'N/A')
                model_name = model.get('modelName', 'N/A')
                input_modalities = ", ".join(model.get('inputModalities', []))
                output_modalities = ", ".join(model.get('outputModalities', []))
                inference_types = model.get('inferenceTypesSupported', [])
                supports_on_demand = 'ON_DEMAND' in inference_types if inference_types else False

                print(f"\nModel ID: {model_id}")
                print(f"Name: {model_name}")
                print(f"Input: {input_modalities}")
                print(f"Output: {output_modalities}")

                if supports_on_demand:
                    print(f"Supports ON_DEMAND inference")
                if model.get('responseStreamingSupported'):
                    print(f"Supports streaming")
    except ClientError as e:
        print(f"Error accessing Bedrock: {e}")
        return

def main():
    parser = argparse.ArgumentParser(
        description="List available Bedrock models in your AWS account"
    )
    parser.add_argument(
        "--region",
        type=str,
        default="eu-west-2",
        help="AWS region (default: eu-west-2)"
    )

    args = parser.parse_args()
    list_available_models(args.region)

if __name__ == "__main__":
    main()
