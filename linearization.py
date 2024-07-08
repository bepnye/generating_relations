from typing import cast
import pdb
import json
import processing

import utils
from classes import Article, Relation, Entity

def linearize_boring(docs: list[Article], dataset: str) -> list[str]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    # i guess we should have the DATASET by this point
    name = 'boring'
    new_words = ['<rel>'] + [f'<{k}>' for k in RELATION_TYPES.keys()] + [f'<{k}>' for k in RELATION_SLOTS]
    json.dump(new_words, open(f'data/{dataset}/{name}/tokens.json', 'w'), indent=2)

    config_data = {
        'input_ids_max_len': 600,
        'labels_max_len': 500,
    }
    json.dump(config_data, open(f'data/{dataset}/{name}/config.json', 'w'), indent=2)

    targets = []
    for article in docs:
        relation_strs = []
        for rel in article.relations:
            rel_pieces = ['<rel>', f'<{rel.rtype}>']
            for entity, slot in zip(rel.entities, rel.slots):
                rel_pieces += [f'<{slot}>', entity.span]
            relation_strs.append(''.join(rel_pieces))
        targets.append(' '.join(relation_strs))
    return targets


def delinearize_boring(linearized_tokens: list[list[int]], tokenizer, dataset: str) -> list[list[Relation]]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    str2token = tokenizer.get_added_vocab()
    rel_token = str2token['<rel>']
    per_doc_relations = []
    for token_seq in linearized_tokens:
        relations = set()
        rel_token_seqs = utils.split_seq(token_seq, rel_token)
        for rel_token_seq in rel_token_seqs:
            # Can't have fewer than the required tokens
            if len(rel_token_seq) < len(RELATION_SLOTS) + 1:
                continue
            rel_type_str = tokenizer.convert_ids_to_tokens(int(rel_token_seq[0])).strip('<>')
            # The first token should be the relation type
            if rel_type_str not in RELATION_TYPES:
                continue
            # we need one head entity
            slot_token_strs = [f'<{slot_name}>' for slot_name in RELATION_SLOTS]
            slot_tokens = [str2token[slot_token] for slot_token in slot_token_strs]
            slot_token_counts = [rel_token_seq.count(slot_token) for slot_token in slot_tokens]
            if not all([count == 1 for count in slot_token_counts]):
                continue
            # the tail can't come before the head
            slot_token_idxs = [rel_token_seq.index(slot_token) for slot_token in slot_tokens]
            valid_idxs = [slot_token_idxs[i] < slot_token_idxs[i+1] for i in range(len(slot_token_idxs)-1)]
            if not all(valid_idxs):
                continue

            # everything seems in order! let's build the relation tuple
            # the start and stop token indices for adjacent entities
            slice_idxs = slot_token_idxs + [len(rel_token_seq)]
            entities = []
            for start, stop in zip(slice_idxs[:-1], slice_idxs[1:]):
                entities.append(Entity('[UNK]', tokenizer.decode(rel_token_seq[start+1:stop], skip_special_tokens=True)))
            relations.add(Relation(rel_type_str, entities, RELATION_SLOTS))
        per_doc_relations.append(list(relations))
    return per_doc_relations

def write_data(articles: list[Article], targets: list[str],
               dataset: str, encoding: str, split: str) -> None:
    article_dicts = [a.to_dict() for a in articles]
    for a_dict, target in zip(article_dicts, targets):
        a_dict['target'] = target
    json.dump(article_dicts, open(f'data/{dataset}/{encoding}/{split}.json', 'w'), indent=2)

def linearize_vertex_ref(docs: list[Article], dataset: str) -> list[str]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    # i guess we should have the DATASET by this point
    name = 'vertex_ref'
    new_words = ['<rel>', '<vertex>'] + \
                [f'<{k}>' for k in RELATION_TYPES.keys()] + \
                [f'<{k}>' for k in RELATION_SLOTS] + \
                [f'<{i}>' for i in range(100)]
    json.dump(new_words, open(f'data/{dataset}/{name}/tokens.json', 'w'), indent=2)

    config_data = {
        'input_ids_max_len': 600,
        'labels_max_len': 500,
    }
    json.dump(config_data, open(f'data/{dataset}/{name}/config.json', 'w'), indent=2)

    outputs = []
    for article in docs:
        relation_strs = []
        vertex_strs = []
        vertices = article.get_entities()
        for x, vertex in enumerate(vertices):
            vertex_strs.append('<vertex>')
            vertex_strs.append(f'<{x}>')
            vertex_strs.append(f'{vertex}')
        for rel in article.relations:
            rel_pieces = ['<rel>', f'<{rel.rtype}>']
            for entity, slot in zip(rel.entities, rel.slots):
                rel_pieces += [f'<{slot}>', f'<{vertices.index(entity)}>']
            relation_strs.append(''.join(rel_pieces))
        target = ' '.join(vertex_strs + relation_strs)
        outputs.append(target)
    return outputs



def delinearize_vertex_ref(linearized_tokens: list[list[int]], tokenizer, dataset: str):
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    str2token = tokenizer.get_added_vocab()
    rel_token = str2token['<rel>']
    vertex_token = str2token['<vertex>']
    per_doc_relations = []
    for y, token_seq in enumerate(linearized_tokens):
        # print(tokenizer.convert_ids_to_tokens(token_seq))
        relations = set()
        vertices = []
        rel_token_seqs = utils.split_seq(token_seq, rel_token)
        vertex_token_seqs = utils.split_seq(rel_token_seqs.pop(0), vertex_token)
        for x, vertex_token_seq in enumerate(vertex_token_seqs):
            # pdb.set_trace()
            if len(vertex_token_seq) < 2:
                continue
            # print(tokenizer.convert_ids_to_tokens(vertex_token_seq))
            vertex_idx = tokenizer.convert_ids_to_tokens(vertex_token_seq.pop(0)).strip('<>')
            # make sure it generates them in order
            if int(vertex_idx) != x:
                continue
            vertex_span = tokenizer.decode(vertex_token_seq)
            vertices.append(vertex_span)
        for rel_token_seq in rel_token_seqs:
            # Can't have fewer than the required tokens
            # pdb.set_trace()
            if len(rel_token_seq) < len(RELATION_SLOTS) + 1:
                continue
            rel_type_str = tokenizer.convert_ids_to_tokens(rel_token_seq[0]).strip('<>')
            # The first token should be the relation type
            if rel_type_str not in RELATION_TYPES:
                continue
            # we need one head entity
            slot_token_strs = [f'<{slot_name}>' for slot_name in RELATION_SLOTS]
            slot_tokens = [str2token[slot_token] for slot_token in slot_token_strs]
            slot_token_counts = [rel_token_seq.count(slot_token) for slot_token in slot_tokens]
            if not all([count == 1 for count in slot_token_counts]):
                continue
            # the tail can't come before the head
            slot_token_idxs = [rel_token_seq.index(slot_token) for slot_token in slot_tokens]
            valid_idxs = [slot_token_idxs[i] < slot_token_idxs[i + 1] for i in range(len(slot_token_idxs) - 1)]
            if not all(valid_idxs):
                continue

            # everything seems in order! let's build the relation tuple
            # the start and stop token indices for adjacent entities
            slice_idxs = slot_token_idxs + [len(rel_token_seq)]
            entities = []
            for start, stop in zip(slice_idxs[:-1], slice_idxs[1:]):
                # pdb.set_trace()
                entities.append(Entity('[UNK]', vertices[int(tokenizer.decode(rel_token_seq[start + 1:stop]).replace('</s>', '').strip('<>'))]))
            relations.add(Relation(rel_type_str, entities, RELATION_SLOTS))
        per_doc_relations.append(list(relations))
    return per_doc_relations


def linearize_boring_evidence(docs: list[Article], dataset: str) -> list[str]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    # i guess we should have the DATASET by this point
    name = 'boring_evidence'
    new_words = ['<rel>', '<ee>', '<es>'] + [f'<{k}>' for k in RELATION_TYPES.keys()] + [f'<{k}>' for k in RELATION_SLOTS]
    json.dump(new_words, open(f'data/{dataset}/{name}/tokens.json', 'w'), indent=2)

    config_data = {
        'input_ids_max_len': 600,
        'labels_max_len': 500,
    }
    json.dump(config_data, open(f'data/{dataset}/{name}/config.json', 'w'), indent=2)

    targets = []
    for article in docs:
        relation_strs = []
        for rel in article.relations:
            rel_pieces = ['<rel>', f'<{rel.rtype}>']
            for entity, slot in zip(rel.entities, rel.slots):
                rel_pieces += [f'<{slot}>', entity.span]
            rel_pieces.append(f'<es><{rel.evidence[0]}><ee><{rel.evidence[1]}>')
            relation_strs.append(''.join(rel_pieces))
        targets.append(' '.join(relation_strs))
    return targets


def delinearize_boring_evidence(linearized_tokens: list[list[int]], tokenizer, dataset: str) -> list[list[Relation]]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    str2token = tokenizer.get_added_vocab()
    rel_token = str2token['<rel>']
    per_doc_relations = []
    for token_seq in linearized_tokens:
        relations = set()
        rel_token_seqs = utils.split_seq(token_seq, rel_token)
        for rel_token_seq in rel_token_seqs:
            # Can't have fewer than the required tokens
            if len(rel_token_seq) < len(RELATION_SLOTS) + 1:
                continue
            rel_type_str = tokenizer.convert_ids_to_tokens(int(rel_token_seq[0])).strip('<>')
            # The first token should be the relation type
            if rel_type_str not in RELATION_TYPES:
                continue
            # we need one head entity
            slot_token_strs = [f'<{slot_name}>' for slot_name in RELATION_SLOTS] + ['<es>', '<ee>']
            slot_tokens = [str2token[slot_token] for slot_token in slot_token_strs]
            slot_token_counts = [rel_token_seq.count(slot_token) for slot_token in slot_tokens]
            if not all([count == 1 for count in slot_token_counts]):
                continue
            # the tail can't come before the head
            slot_token_idxs = [rel_token_seq.index(slot_token) for slot_token in slot_tokens]
            valid_idxs = [slot_token_idxs[i] < slot_token_idxs[i+1] for i in range(len(slot_token_idxs)-1)]
            if not all(valid_idxs):
                continue

            # everything seems in order! let's build the relation tuple
            # the start and stop token indices for adjacent entities

            relation_slice_idxs = slot_token_idxs[:-1]
            evidence_slice_idxs = slot_token_idxs[-2:]
            entities = []
            # need to add logic for evidence
            for start, stop in zip(relation_slice_idxs[:-1], relation_slice_idxs[1:]):
                entities.append(Entity('[UNK]', tokenizer.decode(rel_token_seq[start+1:stop], skip_special_tokens=True)))
            #pdb.set_trace()
            ev_start = tokenizer.decode(rel_token_seq[evidence_slice_idxs[0]+1:evidence_slice_idxs[1]]).strip('<>')
            ev_end = tokenizer.decode(rel_token_seq[evidence_slice_idxs[1]+1:len(rel_token_seq)]).strip('<>')
            relations.add(Relation(rel_type_str, entities, RELATION_SLOTS, [ev_start, ev_end]))
        per_doc_relations.append(list(relations))
    return per_doc_relations


def linearize_vertex_ref_evidence(docs: list[Article], dataset: str) -> list[str]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    # i guess we should have the DATASET by this point
    name = 'vertex_ref'
    new_words = ['<rel>', '<vertex>'] + \
                [f'<{k}>' for k in RELATION_TYPES.keys()] + \
                [f'<{k}>' for k in RELATION_SLOTS] + \
                [f'<{i}>' for i in range(100)]
    json.dump(new_words, open(f'data/{dataset}/{name}/tokens.json', 'w'), indent=2)

    config_data = {
        'input_ids_max_len': 600,
        'labels_max_len': 500,
    }
    json.dump(config_data, open(f'data/{dataset}/{name}/config.json', 'w'), indent=2)

    outputs = []
    for article in docs:
        relation_strs = []
        vertex_strs = []
        vertices = article.get_entities()
        for x, vertex in enumerate(vertices):
            vertex_strs.append('<vertex>')
            vertex_strs.append(f'<{x}>')
            vertex_strs.append(f'{vertex}')
        for rel in article.relations:
            rel_pieces = ['<rel>', f'<{rel.rtype}>']
            for entity, slot in zip(rel.entities, rel.slots):
                rel_pieces += [f'<{slot}>', f'<{vertices.index(entity)}>']
            rel_pieces.append(f'<es><{rel.evidence[0]}><ee><{rel.evidence[1]}>')
            relation_strs.append(''.join(rel_pieces))
        target = ' '.join(vertex_strs + relation_strs)
        outputs.append(target)
    return outputs

def delinearize_vertex_ref_evidence(linearized_tokens: list[list[int]], tokenizer, dataset: str) -> list[list[Relation]]:
    RELATION_TYPES = json.load(open(f'data/{dataset}/rel_types.json'))
    RELATION_SLOTS = json.load(open(f'data/{dataset}/rel_slots.json'))
    str2token = tokenizer.get_added_vocab()
    rel_token = str2token['<rel>']
    vertex_token = str2token['<vertex>']
    per_doc_relations = []
    for y, token_seq in enumerate(linearized_tokens):
        # print(tokenizer.convert_ids_to_tokens(token_seq))
        relations = set()
        vertices = []
        rel_token_seqs = utils.split_seq(token_seq, rel_token)
        vertex_token_seqs = utils.split_seq(rel_token_seqs.pop(0), vertex_token)
        for x, vertex_token_seq in enumerate(vertex_token_seqs):
            # pdb.set_trace()
            if len(vertex_token_seq) < 2:
                continue
            # print(tokenizer.convert_ids_to_tokens(vertex_token_seq))
            vertex_idx = tokenizer.convert_ids_to_tokens(vertex_token_seq.pop(0)).strip('<>')
            # make sure it generates them in order
            if int(vertex_idx) != x:
                continue
            vertex_span = tokenizer.decode(vertex_token_seq)
            vertices.append(vertex_span)
        for rel_token_seq in rel_token_seqs:
            # Can't have fewer than the required tokens
            # pdb.set_trace()
            if len(rel_token_seq) < len(RELATION_SLOTS) + 1:
                continue
            rel_type_str = tokenizer.convert_ids_to_tokens(rel_token_seq[0]).strip('<>')
            # The first token should be the relation type
            if rel_type_str not in RELATION_TYPES:
                continue
            # we need one head entity
            slot_token_strs = [f'<{slot_name}>' for slot_name in RELATION_SLOTS] + ['<es>', '<ee>']
            slot_tokens = [str2token[slot_token] for slot_token in slot_token_strs]
            slot_token_counts = [rel_token_seq.count(slot_token) for slot_token in slot_tokens]
            if not all([count == 1 for count in slot_token_counts]):
                continue
            # the tail can't come before the head
            slot_token_idxs = [rel_token_seq.index(slot_token) for slot_token in slot_tokens]
            valid_idxs = [slot_token_idxs[i] < slot_token_idxs[i + 1] for i in range(len(slot_token_idxs) - 1)]
            if not all(valid_idxs):
                continue

            # everything seems in order! let's build the relation tuple
            # the start and stop token indices for adjacent entities
            relation_slice_idxs = slot_token_idxs[:-1]
            evidence_slice_idxs = slot_token_idxs[-2:]
            entities = []
            for start, stop in zip(relation_slice_idxs[:-1], relation_slice_idxs[1:]):
                entities.append(Entity('[UNK]', vertices[
                    int(tokenizer.decode(rel_token_seq[start + 1:stop]).replace('</s>', '').strip('<>'))]))
            ev_start = tokenizer.decode(rel_token_seq[evidence_slice_idxs[0] + 1:evidence_slice_idxs[1]]).strip(
                    '<>')
            ev_end = tokenizer.decode(rel_token_seq[evidence_slice_idxs[1] + 1:len(rel_token_seq)]).strip('<>')
            relations.add(Relation(rel_type_str, entities, RELATION_SLOTS, [ev_start, ev_end]))
        per_doc_relations.append(list(relations))
    return per_doc_relations



# Runs the encoding funcs for the DocRED train/eval splits, and writes the data to file
# you may need to manually created the destination directory
def write_all_docred():
    dataset = 'docred'
    import processing.docred
    for fname_in, split in [('train_data', 'train'), ('dev', 'eval')]:
        docs = processing.docred.get_docred(f'data/{dataset}/{fname_in}.json')
        for encoding_name, encoding_func in [('boring', linearize_boring), ('vertex_ref', linearize_vertex_ref)]:
            targets = encoding_func(docs, dataset)
            write_data(docs, targets, 'docred', encoding_name, split)

# Runs the encoding funcs for the EvidenceInference train/eval splits, and writes the data to file
# you may need to manually created the destination directory
def write_all_ev_inf():
    dataset = 'evidence_inference'
    import processing.evidence_inference
    for fname_in, split in [('ev_inf_train', 'train'), ('ev_inf_eval', 'eval')]:
        docs = processing.evidence_inference.load_evidence_inference(f'data/{dataset}/{fname_in}.json')
        for encoding_name, encoding_func in [('boring', linearize_boring), ('vertex_ref', linearize_vertex_ref)]:
            targets = encoding_func(docs, dataset)
            write_data(docs, targets, dataset, encoding_name, split)

# Tests to make sure that the process of
#       article.relations -> linearized -> tokenized -> delinearized
# gets you back to the starting relations
def test_linearization(articles, dataset, name, linearization_fn, delinearization_fn):
    # arbitrary choice of tokenizer; it may even be wise to test multiple different ones just in case
    # ultimately, each tokenizer will fail to recreate the true originals in some way (e.g. missing accents)
    # but this isn't a huge issue since the true relations will also be put through the tokenizer during training
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained('t5-small')
    new_tokens = json.load(open(f'data/{dataset}/{name}/tokens.json', 'r'))
    tokenizer.add_tokens(new_tokens)
    linearized_targets = linearization_fn(articles, dataset)
    linearized_tokens = cast(list[list[int]], tokenizer(linearized_targets)['input_ids'])
    delinearized_rels = delinearization_fn(linearized_tokens, tokenizer, dataset)
    all_correct = 0
    for article, d_rels in zip(articles, delinearized_rels):
        # since we've overloaded the __hash__ implementation for Relations, this works!
        if set(article.relations) == set(d_rels):
            all_correct += 1
        else:
            true_strs = set(map(str, article.relations))
            pred_strs = set(map(str, d_rels))
            print('TRUE:')
            for rel in true_strs.difference(pred_strs):
                print('\t', rel)
            print('DECODED:')
            for rel in pred_strs.difference(true_strs):
                print('\t', rel)
            print()
    print(f'All correct = {all_correct}/{len(articles)} = {all_correct/len(articles)}')

def run_tests(name, linearization_fn, delinearization_fn):
    # somewhat awkwardly, the syntax for loading different datasets is a little different
    # TODO: standardize this so we can just loop over dataset names?
    print("Loading articles to test DocRED")
    import processing.docred
    articles = processing.docred.get_docred('data/docred/dev.json')
    input(f"Testing on DocRED {len(articles)=}. Press any key to continue.")
    test_linearization(articles, 'docred', name, linearization_fn, delinearization_fn)
    
    print("Loading articles to test EvidenceInference")
    import processing.evidence_inference
    articles = processing.evidence_inference.load_evidence_inference('data/evidence_inference/ev_inf_eval.json')
    input(f"Testing on EvInf {len(articles)=}. Press any key to continue.")
    test_linearization(articles, 'evidence_inference', name, linearization_fn, delinearization_fn)

# test suites that will run the specific scheme on multiple datasets and print diagnostics
def test_boring():
    run_tests('boring', linearize_boring, delinearize_boring)

def test_vertex_ref():
    run_tests('vertex_ref', linearize_vertex_ref, delinearize_vertex_ref)

def test_boring_evidence():
    run_tests('boring_evidence', linearize_boring_evidence, delinearize_boring_evidence)

def test_vertex_ref_evidence():
    run_tests('vertex_ref_evidence', linearize_vertex_ref_evidence, delinearize_vertex_ref_evidence)

if __name__ == '__main__':
    write_all_docred()
    write_all_ev_inf()

    test_boring()
    test_vertex_ref()