# Industry taxonomy

Synthetic classification taxonomy: **5 Tier 1 / 26 Tier 2 / 77 Tier 3**. This is a curated design, not an official industry standard. 

## Full category tree

### Financial Services

- **Banking**: Retail Banking; Commercial Banking; Universal Banking.
- **Lending**: Consumer Lending; Business Lending; Mortgage Lending.
- **Payments**: Payment Networks; Merchant Payment Processing; Payment Operations Platforms.
- **Insurance**: Life and Health Insurance; Property and Casualty Insurance; Insurance Brokerage.
- **Investment Services**: Asset Management; Securities Brokerage; Investment Banking.

### Healthcare and Life Sciences

- **Care Providers**: Hospitals; Outpatient Care; Dental Care.
- **Pharmaceuticals**: Integrated Pharmaceuticals; Clinical Drug Development; Generic Medicines.
- **Biotechnology**: Cell and Gene Therapies; Biologic Therapeutics; Research Tools and Reagents.
- **Medical Devices**: Surgical Devices; Imaging Equipment; Monitoring and Therapeutic Devices.
- **Diagnostics**: Clinical Laboratories; Molecular Diagnostics; Diagnostic Imaging Services.

### Industrials

- **Aerospace and Defense**: Commercial Aircraft; Defense and Space Systems; Diversified Aerospace and Defense.
- **Machinery**: Industrial Machinery; Agricultural Machinery; Construction and Mining Equipment.
- **Electrical Equipment**: Power Distribution Equipment; Industrial Controls; Batteries and Energy Storage.
- **Construction and Engineering**: Building Construction; Civil Infrastructure Construction; Engineering and Design Services.
- **Transportation and Logistics**: Passenger Transportation; Freight Transportation; Logistics and Warehousing.

### Consumer Goods

- **Food**: Packaged Foods; Snacks and Confectionery; Dairy and Alternative Foods.
- **Beverages**: Nonalcoholic Beverages; Alcoholic Beverages; Coffee and Tea Products.
- **Apparel and Footwear**: Apparel; Footwear; Accessories and Bags.
- **Household Products**: Home Furnishings; Household Appliances; Household Cleaning Products.
- **Personal Care and Beauty**: Skincare and Cosmetics; Haircare; Personal Hygiene.

### Technology

- **Software**: Customer Relationship Software; Work and Product Management Software; Cybersecurity Software.
- **Computing Hardware**: Personal Computing Devices; Servers and Storage Hardware; Network Equipment.
- **Semiconductors**: Fabless Chip Design; Chip Manufacturing; Semiconductor Equipment.
- **IT Services**: IT Consulting and Integration; Custom Software Development; Managed IT Services.
- **Cloud and Data Infrastructure**: Cloud Compute Infrastructure; Managed Data Platforms; Data Centers and Colocation.

## Design and boundaries

Each node has a local description and explicit exclusions. Generated full-path definitions inherit all three levels. Broad sector membership does not guarantee a supported leaf: unknown activities may remain outside this intentionally incomplete taxonomy.

Banking takes priority for deposit-taking businesses. Payment infrastructure is assigned to Financial Services even when delivered as software. Pharmaceuticals versus Biotechnology depends on the described portfolio or modality, not the word biotech. Application SaaS belongs to Software; renting compute or managed data infrastructure belongs to Cloud and Data Infrastructure.

Boeing now has a diversified aerospace label, so commercial aircraft and defense activities do not force an arbitrary single-segment choice. A company with unresolved competing activities should abstain rather than infer revenue leadership.

## Existing company relabeling

| Company | V2 path | Industry code |
|---|---|---|
| Salesforce | Technology → Software → Customer Relationship Software | `000061` |
| Linear | Technology → Software → Work and Product Management Software | `000062` |
| Boeing | Industrials → Aerospace and Defense → Diversified Aerospace and Defense | `000033` |
| Boom Supersonic | Industrials → Aerospace and Defense → Commercial Aircraft | `000031` |
| The Coca-Cola Company | Consumer Goods → Beverages → Nonalcoholic Beverages | `000049` |
| Liquid Death | Consumer Goods → Beverages → Nonalcoholic Beverages | `000049` |
| Visa | Financial Services → Payments → Payment Networks | `000007` |
| Modern Treasury | Financial Services → Payments → Payment Operations Platforms | `000009` |
| Pfizer | Healthcare and Life Sciences → Pharmaceuticals → Integrated Pharmaceuticals | `000019` |
| Formation Bio | Healthcare and Life Sciences → Pharmaceuticals → Clinical Drug Development | `000020` |

## Files and use

- `taxonomy.json`: source descriptions, relationships, boundaries, and fixed industry codes.
- `PATH_DEFINITIONS.md` / `path_definitions.json`: generated combined definitions.
- `company_inputs.json`: sourced company descriptions for evaluation.
- `expected_labels.json`: evaluation answers; never send to the model.
- `edge_cases.json`: synthetic tests.

Run from the project root:

```sh
source .venv/bin/activate
python scripts/build_industry_definitions.py --data-dir data
python evaluate_industry.py --data-dir data --dry-run
python pipeline_e2e.py --data-dir data --dry-run
```

Remove `--dry-run` only when ready for live API evaluation.

## Limits

Ten existing companies cover only a subset of these 77 leaves. Uncovered labels are not tested for accuracy. Add sibling-confusion cases and independently labeled companies before judging quality. Industry codes are fixed within v2 and are not comparable across taxonomy versions. The larger flat prompt may increase tokens and latency; 79 choices (including two abstentions) remain below the 255-option limit, but check actual context usage during a live run. Broad accuracy has not been established for v2.
