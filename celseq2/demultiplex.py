# coding: utf-8
from collections import Counter

import csv
import os
import argparse

from celseq2.helper import filehandle_fastq_gz, print_logger


def bc_dict_seq2id(bc_index_fpath):
    """ dict[barcode_seq] = barcode_id """
    out = dict()
    with open(bc_index_fpath, 'rt') as fin:
        freader = csv.reader(fin, delimiter='\t')
        next(freader)
        out = {row[1]: int(row[0]) for row in freader}
    return(out)


def bc_dict_id2seq(bc_index_fpath):
    out = dict()
    with open(bc_index_fpath, 'rt') as fin:
        freader = csv.reader(fin, delimiter='\t')
        next(freader)
        out = {row[0]: int(row[1]) for row in freader}
    return(out)


def demultiplexing(read1_fpath, read2_fpath, dict_bc_seq2id,
                   outdir,
                   len_umi=6, len_bc=6, len_tx=35, bc_qual_min=10,
                   is_gzip=True,
                   do_bc_rev_complement=False,
                   do_tx_rev_complement=False,
                   verbose=False):
    """
    Demultiplexing to fastq files based on barcode sequence.


    """
    if is_gzip:
        fh_umibc = filehandle_fastq_gz(read1_fpath)
        fh_tx = filehandle_fastq_gz(read2_fpath)
    else:
        fh_umibc = open(read1_fpath, 'rt')
        fh_tx = open(read2_fpath, 'rt')

    sample_counter = Counter()

    bc_fhout = dict()
    for bc_seq, bc_id in dict_bc_seq2id.items():
        bc_fhout[bc_seq] = os.path.join(outdir, 'BC-{}-{}.fastq'.format(bc_id,
                                                                        bc_seq))
    bc_fhout['UNKNOWNBC_R1'] = os.path.join(outdir, 'UNKNOWNBC_R1.fastq')
    bc_fhout['UNKNOWNBC_R2'] = os.path.join(outdir, 'UNKNOWNBC_R2.fastq')

    for bc_seq, v in bc_fhout.items():
        bc_fhout[bc_seq] = open(v, 'w')

    i = 0
    while(True):
        if verbose and i % 1000000 == 0:
            print_logger('Processing {:,} reads...'.format(i))
        try:
            umibc_name = next(fh_umibc).rstrip()
            umibc_seq = next(fh_umibc).rstrip()
            next(fh_umibc)
            umibc_qualstr = next(fh_umibc).rstrip()
            tx_name = next(fh_tx).rstrip()
            tx_seq = next(fh_tx).rstrip()
            next(fh_tx)
            tx_qualstr = next(fh_tx).rstrip()
            i += 1
        except StopIteration:
            break

#         Quality check? or user should feed good files
#         if not (umibc_name and umibc_seq and umibc_qualstr and tx_name and tx_seq and tx_qualstr):
#             raise Exception('FastQError: Possible Broken Fastq. Check pair-{}.\n'.format(i+1))
#         if len(umibc_seq) != len(umibc_qualstr) or len(tx_seq) != len(tx_qualstr):
#             raise Exception('FastQError: Possible multi-line Fastq. Convert to 4-line please.\n')
#         if umibc_name.split()[0] != tx_name.split()[0]:
#             raise Exception('FastQError: Reads are not paired at pair-{}.\n'.format(i+1))

        sample_counter['total'] += 1

        if len(umibc_seq) < len_umi + len_bc:
            continue

        umibc_min_qual = min((ord(c)-33 for c in umibc_qualstr[:(len_umi + len_bc)]))
        if umibc_min_qual < bc_qual_min:
            continue

        sample_counter['qualified'] += 1

        umi, cell_bc = umibc_seq[0:len_umi], umibc_seq[len_umi:(len_umi + len_bc)]
        try:
            fhout = bc_fhout[cell_bc]
        except KeyError:
            fhout = bc_fhout['UNKNOWNBC_R1']
            fhout.write('{}\n{}\n{}\n{}\n'.format(umibc_name, umibc_seq,
                                                  "+", umibc_qualstr))
            fhout = bc_fhout['UNKNOWNBC_R2']
            fhout.write('{}\n{}\n{}\n{}\n'.format(tx_name, tx_seq,
                                                  "+", tx_qualstr))
            sample_counter['unknown'] += 1
            continue

#         if len(tx_seq) < len_tx:
#             continue
        if len(tx_seq) > len_tx:
            tx_seq, tx_qualstr = tx_seq[:len_tx], tx_qualstr[:len_tx]
        read_name = '@BC-{}_UMI-{}'.format(cell_bc, umi)
        fhout.write('{}\n{}\n{}\n{}\n'.format(read_name, tx_seq, "+", tx_qualstr))
        sample_counter[cell_bc] += 1
        sample_counter['saved'] += 1


    sample_counter['unqualified'] = sample_counter['total'] - sample_counter['qualified']
    for _, v in bc_fhout.items():
        v.close()
    fh_umibc.close()
    fh_tx.close()

    return(sample_counter)


def write_demultiplexing(stats, dict_bc_seq2id, stats_fpath):
    if stats_fpath is None:
        stats_fpath = os.path.join('demultiplexing.log')
    try:
        fh_stats = open(stats_fpath, 'w')
    except:
        raise
    fh_stats.write('BC\tReads(#)\tReads(%)\n')
    for k, v in dict_bc_seq2id.items():
        fh_stats.write('{:03d}-{}\t{:,}\t{:06.2f}\n'.format(v, k, stats[k],
                                                            stats[k]/stats['total']*100))
    fh_stats.write('{}\t{}\t{:06.2f}\n'.format('saved',
                                               stats['saved'],
                                               stats['saved']/stats['total']*100))
    fh_stats.write('{}\t{}\t{:06.2f}\n'.format('unknown',
                                               stats['unknown'],
                                               stats['unknown']/stats['total']*100))
    fh_stats.write('{}\t{}\t{:06.2f}\n'.format('qualified',
                                               stats['qualified'],
                                               stats['qualified']/stats['total']*100))
    fh_stats.write('{}\t{}\t{:06.2f}\n'.format('unqualified',
                                               stats['unqualified'],
                                               stats['unqualified']/stats['total']*100))
    fh_stats.write('{}\t{}\t{:06.2f}\n'.format('total',
                                               stats['total'],
                                               stats['total']/stats['total']*100))


def main():
    parser = argparse.ArgumentParser(description= __doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    # parser.add_argument('sample_sheet', type=str)
    parser.add_argument('read1_fpath', type=str)
    parser.add_argument('read2_fpath', type=str)
    parser.add_argument('--bc_index', type=str, metavar='FILENAME',
                        help='File path to barcode used')
    parser.add_argument('--min-bc-quality', metavar='N', type=int, default=10,
                        help='Minimal quality for barcode reads (default=10)')
    parser.add_argument('--out-dir', metavar='DIRNAME', type=str, default='.',
                        help='Output directory. Defaults to current directory')
    parser.add_argument('--is-gzip', dest='is_gzip', action='store_true')
    parser.add_argument('--not-gzip', dest='is_gzip', action='store_false')
    parser.set_defaults(is_gzip=True)
    parser.add_argument('--stats-file', metavar='STATFILE',
                        type=str, default='demultiplexing.log',
                        help='Statistics (default: demultiplexing.log)')
    parser.add_argument('--umi-length', metavar='N', type=int, default=0,
                        help='Length of UMI (default=0, e.g. no UMI)')
    parser.add_argument('--bc-length', metavar='N', type=int, default=8,
                        help='Length of CELSeq barcode (default=8)')
    parser.add_argument('--cut-length', metavar='N', type=int, default=35,
                        help='Length of mapped read (default=35)')
    parser.add_argument('--verbose', dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)

    args = parser.parse_args()

    bc_dict = bc_dict_seq2id(args.bc_index)
    print_logger('Demultiplexing starts ...')
    out = demultiplexing(read1_fpath=args.read1_fpath,
                         read2_fpath=args.read2_fpath,
                         outdir=args.out_dir, dict_bc_seq2id=bc_dict,
                         len_umi=args.umi_length,
                         len_bc=args.bc_length,
                         len_tx=args.cut_length,
                         bc_qual_min=args.min_bc_quality,
                         is_gzip=args.is_gzip,
                         do_bc_rev_complement=False,
                         do_tx_rev_complement=False,
                         verbose=args.verbose)
    print_logger('Demultiplexing ends ...')
    write_demultiplexing(out, bc_dict, args.stats_file)


if __name__ == "__main__":
    main()