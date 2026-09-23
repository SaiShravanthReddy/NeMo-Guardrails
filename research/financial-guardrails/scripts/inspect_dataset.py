import argparse

from financial_guardrails.datasets import inspect_json_dataset


def main():
    parser = argparse.ArgumentParser(description="Create a content-free dataset intake manifest")
    parser.add_argument("path")
    args = parser.parse_args()
    print(inspect_json_dataset(args.path).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
