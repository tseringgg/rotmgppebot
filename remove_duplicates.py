import csv
import os

def remove_duplicates_from_csv():
    input_file = "rotmg_loot_drops_updated.csv"
    output_file = "rotmg_loot_drops_no_dupes.csv"
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found!")
        return
    
    seen_rows = set()
    unique_rows = []
    duplicate_count = 0
    
    # Read the input CSV
    with open(input_file, 'r', newline='', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        
        # Process each row
        for row in reader:
            # Convert row to tuple so it can be added to set
            row_tuple = tuple(row)
            
            if row_tuple not in seen_rows:
                seen_rows.add(row_tuple)
                unique_rows.append(row)
            else:
                duplicate_count += 1
    
    # Write the unique rows to output CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(unique_rows)
    
    print(f"✅ Duplicate removal complete!")
    print(f"📊 Original file: {len(unique_rows) + duplicate_count} rows")
    print(f"📊 Unique rows: {len(unique_rows)} rows")
    print(f"📊 Duplicates removed: {duplicate_count} rows")
    print(f"💾 Output saved to: {output_file}")

if __name__ == "__main__":
    remove_duplicates_from_csv()